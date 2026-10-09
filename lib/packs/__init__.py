"""
Knowledge packs: domain knowledge that build/index.py applies to a corpus.

A pack is a module in this folder. Every attribute is optional:

  DESCRIPTION      one line shown by `python -m lib.packs`
  REQUIRES         other packs loaded first, e.g. ["government"]
  ENTITIES         {type: [(canonical name, [aliases], description), ...]}   (types: lib.text.TYPES)
  DESCRIPTIONS     {"type:Name": "description"} overrides for entities defined by earlier packs
  IDEAS            [(theme name, [regex, ...], description), ...]   themes matched by regex
  MIN_IDEA_HITS    a document is tagged with a theme when it has this many regex hits (default 3)
  STRIP_PATTERNS   [regex, ...] boilerplate removed before entity matching (classification banners ...)
  CODENAME_STOP    set/str of ALL-CAPS tokens that are never codenames
  MARKING_WORDS    [word, ...] markings whose OCR misspellings must not become codenames
  SUPPRESS_ALIASES [alias, ...] names that don't match, whichever pack defined them (the entity keeps its other
                   names; one left with none is dropped): short names that collide with the jargon or OCR noise
                   of this kind of material ("ETA" in cables). Applies only when every pack a corpus loads is
                   this pack or one it requires, as a corpus that also loads e.g. sigint is not purely this kind
                   of material. Corpus configs add names with [index] suppress_aliases and exempt names from
                   pack suppressions with [index] keep_aliases.
  ORIGIN_RULES     [(priority, regex, label[, target[, unless]])] or dicts; lowest priority wins;
                   target "head" (first 20k chars, default) or "path"
  CLASSIFICATION_RULES  [(priority, regex, label)], tested on the first 200k chars
  DATE_HINTS       [(priority, fn(text, relpath, corpus) -> (date, source) | None)]
  PUBLISHED_DATE   fn(relpath) -> "YYYY-MM-DD" | ""     publication date encoded in file names
  METADATA         [fn(doc, text, meta, corpus)]  parse structured headers: set meta["title"/"date"/
                   "date_source"/"origin"/"classification"/"author"], meta["fields"][k] = v,
                   append entity refs to meta["entities"] and [src, type, dst] to meta["relations"]
  TIMELINE_PRESETS [(label, "Name A|Name B|...")]

Packs are merged in the order listed in the corpus config. Entities with the same type and name
are merged (aliases unioned); the description from the last pack wins. Run
`python -m lib.packs --check core government sigint` to find aliases claimed by two entities.
"""
import importlib
import os
import pkgutil
import re

HERE = os.path.dirname(os.path.abspath(__file__))


def available():
    return sorted(m.name for m in pkgutil.iter_modules([HERE]) if not m.name.startswith("_"))


def _import(name):
    # import first and list the folder only for the error: listing it on every call is slow on external drives
    if name.isidentifier() and not name.startswith("_"):
        try:
            return importlib.import_module(f"lib.packs.{name}")
        except ModuleNotFoundError as e:
            if e.name != f"lib.packs.{name}":
                raise
    raise SystemExit(f"Unknown knowledge pack {name!r}. Available: {', '.join(available())}")


def _resolve_order(names):
    order, seen = [], set()

    def visit(n, stack=()):
        if n in seen:
            return
        if n in stack:
            raise SystemExit(f"Circular pack dependency: {' -> '.join(stack + (n,))}")
        mod = _import(n)
        for dep in getattr(mod, "REQUIRES", []):
            visit(dep, stack + (n,))
        seen.add(n)
        order.append(n)

    for n in names:
        visit(n)
    return order


class Knowledge:
    """The merged contents of a list of packs. keep_aliases: names exempt from the packs' SUPPRESS_ALIASES."""

    def __init__(self, names, keep_aliases=()):
        self.packs = _resolve_order(names)
        self.entities = {}          # key -> {key, name, type, aliases (list), description}
        self.ideas = []
        self.min_idea_hits = 3
        self.strip_patterns = []
        self.codename_stop = set()
        self.marking_words = []
        self.origin_rules = []      # (priority, compiled, label, target, unless)
        self.classification_rules = []
        self.date_hints = []
        self.published_date = []
        self.metadata = []
        self.timeline_presets = []
        seen_rules = set()

        def once(tag, item):
            k = (tag, item if not callable(item) else id(item))
            if k in seen_rules:
                return False
            seen_rules.add(k)
            return True

        owner = {}                  # alias (as the matcher sees it) -> first entity that claimed it
        suppressed = []

        for name in self.packs:
            mod = _import(name)
            for etype, items in getattr(mod, "ENTITIES", {}).items():
                for canon, aliases, desc in items:
                    key = f"{etype}:{canon}"
                    e = self.entities.get(key)
                    if e is None:
                        e = self.entities[key] = dict(key=key, name=canon, type=etype, description=desc,
                                                      aliases=sorted(set([canon] + list(aliases))), pack=name)
                    else:
                        # a later pack extends an entity: don't let it take aliases that a more specific
                        # entity already owns (sigint's "U.S. Congress" must not swallow "SSCI")
                        extra = {a for a in aliases if owner.get(_alias_key(a), key) == key}
                        e["aliases"] = sorted(set(e["aliases"]) | extra)
                        if desc:
                            e["description"] = desc
                    for a in e["aliases"]:
                        owner.setdefault(_alias_key(a), key)
            for key, desc in getattr(mod, "DESCRIPTIONS", {}).items():
                if key in self.entities:
                    self.entities[key]["description"] = desc
            for idea in getattr(mod, "IDEAS", []):
                if once("idea", idea[0]):
                    self.ideas.append(idea)
            self.min_idea_hits = getattr(mod, "MIN_IDEA_HITS", self.min_idea_hits)
            for p in getattr(mod, "STRIP_PATTERNS", []):
                if once("strip", p):
                    self.strip_patterns.append(re.compile(p))
            stop = getattr(mod, "CODENAME_STOP", set())
            self.codename_stop |= set(stop.split() if isinstance(stop, str) else stop)
            if set(self.packs) <= set(_resolve_order([name])):
                suppressed += getattr(mod, "SUPPRESS_ALIASES", [])
            for w in getattr(mod, "MARKING_WORDS", []):
                if w not in self.marking_words:
                    self.marking_words.append(w)
            for r in getattr(mod, "ORIGIN_RULES", []):
                rule = normalize_origin_rule(r)
                if once("origin", (rule[0], rule[1].pattern, rule[2], rule[3])):
                    self.origin_rules.append(rule)
            for prio, pat, label in getattr(mod, "CLASSIFICATION_RULES", []):
                if once("class", (pat, label)):
                    self.classification_rules.append((prio, re.compile(pat), label))
            for prio, fn in getattr(mod, "DATE_HINTS", []):
                if once("date", fn):
                    self.date_hints.append((prio, fn))
            fn = getattr(mod, "PUBLISHED_DATE", None)
            if fn and once("pub", fn):
                self.published_date.append(fn)
            for fn in getattr(mod, "METADATA", []):
                if once("meta", fn):
                    self.metadata.append(fn)
            for p in getattr(mod, "TIMELINE_PRESETS", []):
                if once("preset", tuple(p)):
                    self.timeline_presets.append(tuple(p))
        self.origin_rules.sort(key=lambda r: r[0])
        self.classification_rules.sort(key=lambda r: r[0])
        self.date_hints.sort(key=lambda r: r[0])
        keep = {_alias_key(a) for a in keep_aliases}
        self.suppress_aliases([a for a in suppressed if _alias_key(a) not in keep])

    def suppress_aliases(self, aliases):
        """Stop these names from matching; an entity left with no names is dropped."""
        drop = {_alias_key(a) for a in aliases}
        if not drop:
            return
        for key in list(self.entities):
            e = self.entities[key]
            e["aliases"] = [a for a in e["aliases"] if _alias_key(a) not in drop]
            if not e["aliases"]:
                del self.entities[key]

    def add_origin_rules(self, rules):
        """Rules from a corpus config ([[metadata.origin_rules]])."""
        for r in rules:
            self.origin_rules.append(normalize_origin_rule(r))
        self.origin_rules.sort(key=lambda r: r[0])

    def alias_conflicts(self):
        """Aliases claimed by more than one entity (the first one registered wins at match time)."""
        owner, out = {}, []
        for key, e in self.entities.items():
            for a in e["aliases"]:
                k = _alias_key(a)
                if k in owner and owner[k] != key:
                    out.append((a, owner[k], key))
                owner.setdefault(k, key)
        return out


def _alias_key(a):
    """How the matcher compares an alias: exact for one word / ALL CAPS / digits, else lowercase."""
    return a if (len(a.split()) == 1 or a.isupper() or any(c.isdigit() for c in a)) else a.lower()


def normalize_origin_rule(r):
    if isinstance(r, dict):
        prio, pat, label = r.get("priority", 50), r["pattern"], r["label"]
        target, unless = r.get("target", "head"), r.get("unless")
    else:
        prio, pat, label, *rest = r
        target = rest[0] if rest else "head"
        unless = rest[1] if len(rest) > 1 else None
    return (prio, re.compile(pat), label, target, re.compile(unless) if unless else None)


def load(names, keep_aliases=()):
    return Knowledge(names, keep_aliases)


def timeline_presets(names):
    """The packs' TIMELINE_PRESETS in load order, without building their merged knowledge (fast enough for
    every page view; Knowledge(names).timeline_presets holds the same list)."""
    out = []
    for name in _resolve_order(names):
        for p in getattr(_import(name), "TIMELINE_PRESETS", []):
            if tuple(p) not in out:
                out.append(tuple(p))
    return out


