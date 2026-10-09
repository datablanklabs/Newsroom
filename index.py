"""
Stage 2: build the SQLite search index + entity graph for a corpus from data/<corpus>/extracted/.

  .venv/bin/python build/index.py --corpus snowden [--no-ner]

Creates data/<corpus>/index.db with:
  documents      one row per unique document (identical files folded in)
  pages          per-page text (+ FTS5 index pages_fts, docs_fts for titles)
  entities       people, agencies, organizations, companies, programs, technologies, places,
                 themes and identifiers: from the knowledge packs (curated), auto-detected codenames,
                 spaCy NER, patterns (emails, IBANs) and structured metadata (email headers, records)
  mentions       entity x document x page
  edges          entity co-occurrence (same document, within a page window) with NPMI
  relations      typed links from structured data (sender -> recipient, officer -> company ...)

Documents are streamed through SQLite in three passes (dedupe, metadata + pages, entities), so
memory stays flat for corpora with hundreds of thousands of documents.
"""
import argparse
import collections
import hashlib
import itertools
import json
import math
import os
import re
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, PROJECT)
from lib import packs  # noqa: E402
from lib.config import load_corpus  # noqa: E402
from lib.dates import MONTHS  # noqa: E402
from lib.text import (DICT_WORDS, Matcher, is_allcaps, looks_like_company, norm_ws, normalize_org,  # noqa: E402
                      normalize_person, plain, tidy_org, tokenize)


# =========================================================================== document metadata

def prettify_filename(fn, title_strip):
    base = os.path.splitext(os.path.basename(fn))[0]
    if title_strip:
        base = re.sub(title_strip, "", base, flags=re.I)
    base = base.replace("_", " ").replace("-", " ")
    return norm_ws(base) or fn


JUNK_TITLE = re.compile(r"(?i)^(?:microsoft|untitled|slide ?\d|presentation|document\d*|powerpoint|pdf|title|print|\W*$|"
                        r"[\w\-]+\.(?:pdf|ppt|pptx|doc|docx)$|[a-f0-9\-]{16,}$)")


def make_title(doc, text_first, title_strip):
    meta_title = (doc.get("pdf_meta") or {}).get("title", "")
    meta_title = re.sub(r"<[^>]+>", "", meta_title)
    meta_title = re.sub(r"^\s*\([A-Z/ ]{1,30}\)\s*", "", meta_title)   # (S//SI) prefix
    meta_title = re.sub(r"^Microsoft (?:PowerPoint|Word) - ", "", meta_title)
    meta_title = norm_ws(meta_title)
    if meta_title and len(meta_title) > 6 and not JUNK_TITLE.match(meta_title):
        return meta_title[:200]
    if doc["kind"] == "html":
        first = norm_ws(text_first[:200])
        return first[:120] if first else prettify_filename(doc["relpath"], title_strip)
    if doc.get("member"):
        return prettify_filename(doc["member"], title_strip)
    return prettify_filename(doc["relpath"].replace(" (page scans)", ""), title_strip)


def file_part(d):
    """The file a document comes from: records and mailbox messages carry '#<row>' after the file name."""
    src = d.get("src") or {}
    if "record" in src or "mbox" in src:
        return d["relpath"].rsplit("#", 1)[0]
    return d["relpath"]


def collection_of(relpath, md):
    if "!/" in relpath:   # inside an archive: name the collection after the archive
        name = os.path.basename(relpath.split("!/")[0])
        name = re.sub(r"(?i)\.(zip|7z|rar|tar|tgz|tbz2?|txz|tar\.(gz|bz2|xz))$", "", name)
        return md["collection_aliases"].get(name, name)
    parts = relpath.split(os.sep)
    depth = md["collection_depth"]
    if len(parts) <= 1:
        return "(top level)"
    name = "/".join(parts[:min(depth, len(parts) - 1)])
    return md["collection_aliases"].get(name, name)


def publisher_of(relpath, rules):
    for pat, name in rules:
        if re.search(pat, relpath):
            return name
    return ""


def _valid(y, mo, d, C):
    return C.dates["min_year"] <= y <= C.dates["max_year"] and 1 <= mo <= 12 and 1 <= d <= 31


def date_from_filename(fn, C):
    base = os.path.basename(fn)
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", base)
    if m and _valid(int(m.group(1)), int(m.group(2)), int(m.group(3)), C):
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(?i)(?<![a-z0-9])(\d{1,2})[_\- ]?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[_\- ]?(\d{4}|\d{2})(?![0-9])", base)
    if m:
        y = int(m.group(3)); y = y + 2000 if y < 100 else y
        mo = MONTHS[m.group(2).lower()]
        if _valid(y, mo, int(m.group(1)), C):
            return f"{y:04d}-{mo:02d}-{int(m.group(1)):02d}"
    m = re.search(r"(?<!\d)((?:19|20)\d{2})(0[1-9]|1[0-2])([0-3]\d)(?!\d)", base)
    if m and _valid(int(m.group(1)), int(m.group(2)), int(m.group(3)), C):
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


TEXT_DATE_PATTERNS = [
    re.compile(r"(?i)\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+((?:19|20)\d{2})\b"),
    re.compile(r"(?i)\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+((?:19|20)\d{2})\b"),
]


def date_from_text(text, relpath, C, K):
    """Returns (date, source): pack hints first (exact header dates, estimates), then the first date in the text."""
    for _, fn in K.date_hints:
        r = fn(text, relpath, C)
        if r:
            return r
    lo, hi = C.dates["text_min_year"], C.dates["text_max_year"]
    for pat in TEXT_DATE_PATTERNS:
        m = pat.search(text[:6000])
        if m:
            g = m.groups()
            if g[0].isdigit():
                d, mon, y = int(g[0]), g[1], int(g[2])
            else:
                mon, d, y = g[0], int(g[1]), int(g[2])
            mo = MONTHS[mon[:3].lower()]
            if _valid(y, mo, d, C) and lo <= y <= hi:
                return f"{y:04d}-{mo:02d}-{d:02d}", "first date in text (est.)"
    return "", ""


def classification_of(text, K):
    t = text[:200000]
    for _, rx, label in K.classification_rules:
        if rx.search(t):
            return label
    return ""


def origin_of(text, relpath, kind, C, K):
    head = text[:20000]
    if kind == "html":
        return C.metadata["html_origin"]
    for _, rx, label, target, unless in K.origin_rules:
        hay = relpath if target == "path" else (text[:3000] if target == "top" else head)
        if rx.search(hay) and not (unless and unless.search(head)):
            return label
    return C.metadata["default_origin"]


AUTHOR_RE = re.compile(r"FROM:\s*\n?\s*([^\n]{3,120})\n\s*([^\n]{0,120})")


def author_line(text):
    m = AUTHOR_RE.search(text[:3000])
    if not m:
        return ""
    a, b = norm_ws(m.group(1)), norm_ws(m.group(2))
    if b.lower().startswith("run date"):
        b = ""
    return norm_ws(f"{a} — {b}" if b else a)[:200]


# =========================================================================== codename detection

def _edit_distance(a, b):
    if abs(len(a) - len(b)) > 2:
        return 99
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _segments_into_words(w, words, min_part=3):
    """True if an all-caps token splits into >= 2 dictionary words (WEALTHYCLUSTER -> WEALTHY+CLUSTER)."""
    n = len(w)
    ok = [False] * (n + 1)
    parts = [0] * (n + 1)
    ok[0] = True
    for i in range(n):
        if not ok[i]:
            continue
        for j in range(i + min_part, n + 1):
            if w[i:j] in words and (not ok[j] or parts[j] < parts[i] + 1):
                ok[j] = True
                parts[j] = parts[i] + 1
    return ok[n] and parts[n] >= 2


class CodenameStats:
    """All-caps tokens used (almost) exclusively in caps across >= 2 documents. known_upper: the all-caps
    tokens of pack aliases, which are entities already."""
    word_re = re.compile(r"\b[A-Za-z]{5,}\b")

    def __init__(self, known_upper=()):
        self.known = set(known_upper)
        self.caps_n = collections.Counter()
        self.caps_docs = collections.defaultdict(set)
        self.caps_textlayer = set()                    # seen on a text-layer page
        # ... of two or more documents: only these skip the misreading check, as many scans carry an embedded
        # OCR layer, which extract.py cannot tell from born-digital text, and one such page proves little
        self.caps_textlayer_multi = set()
        self.textlayer_first = {}                      # token -> first document with it on a text-layer page
        self.other_n = collections.Counter()
        self.known_n = collections.Counter()           # pack tokens on ALL-CAPS pages, which add() never sees

    def add(self, doc_id, text, is_ocr):
        for w in self.word_re.findall(text):
            if w.isupper():
                self.caps_n[w] += 1
                self.caps_docs[w].add(doc_id)
                if not is_ocr and w not in self.caps_textlayer_multi:
                    self.caps_textlayer.add(w)
                    if self.textlayer_first.setdefault(w, doc_id) != doc_id:
                        self.caps_textlayer_multi.add(w)
            else:
                self.other_n[w.upper()] += 1

    def add_allcaps(self, text):
        """An ALL-CAPS page (old cables) says nothing about codenames, but shows how common the known ones are."""
        for w in self.word_re.findall(text):
            if w in self.known:
                self.known_n[w] += 1

    # letters OCR confuses on typewritten pages (REFORT, CHILOREN, SEGRET, GOVERNWENT, SIGHATURE ...)
    OCR_CONFUSIONS = {frozenset(p) for p in
                      "MW MN NH HR HN DO OQ OC CG PF FE BS BE BR RP RK LI IT UV VW VY KX EC OU".split()}

    @classmethod
    def _ocr_variant(cls, w, v):
        """w is v with one letter dropped, added, or swapped for a look-alike."""
        if len(w) != len(v):
            return True
        diff = [(a, b) for a, b in zip(w, v) if a != b]
        return len(diff) == 1 and frozenset(diff[0]) in cls.OCR_CONFUSIONS

    def _freq(self, w):
        return self.caps_n[w] + self.other_n[w] + self.known_n[w]

    def _misreadings(self, cands):
        """The candidates that are a misreading of a word far more common in this corpus, or of a known
        codename: REFORT (REPORT), CHILOREN (CHILDREN), SEGRET (SECRET), SECTONK (SECTION), JEWAVE (JMWAVE).
        Two words are neighbours if dropping at most one letter from each makes them equal. A look-alike
        letter needs a word 3x as common; any other change one 20x as common (SPECHAL: SPECIAL is 800x), so
        FIREWALK (FIREWALL is only 7x as common, and K is no look-alike for L) stays a codename. Other words
        must be seen 10 times; a known codename also counts on ALL-CAPS pages and needs no minimum, but it must
        be used, so a cryptonym one letter from an unused pack name (AMWHIP, AMWHIM) is kept. Only the
        candidates' deletion neighbourhoods are indexed (SymSpell style); the vocabulary streams past them."""
        def deletes(w):
            return {w} | {w[:i] + w[i + 1:] for i in range(len(w))}
        by_delete = collections.defaultdict(list)
        for w in cands:
            for d in deletes(w):
                by_delete[d].append(w)
        bad = set()
        vocab = itertools.chain(self.caps_n, (v for v in self.other_n if v not in self.caps_n),
                                (v for v in self.known_n if v not in self.caps_n and v not in self.other_n))
        for v in vocab:
            fv = self._freq(v)
            if fv < 10 and v not in self.known:
                continue
            for d in deletes(v):
                for w in by_delete.get(d, ()):
                    if w != v and w not in bad and fv >= (3 if self._ocr_variant(w, v) else 20) * self._freq(w):
                        bad.add(w)
        return bad

    def detect(self, K):
        english = {w.upper() for w in DICT_WORDS}
        english_short = {e for e in english if len(e) >= 3 and e.isalpha()}
        found, unsure = {}, []
        for w, c in self.caps_n.items():
            df = len(self.caps_docs[w])
            if df < 2 or w in K.codename_stop or w in self.known:
                continue
            if re.search(r"SECRE|NOFOR|CLASSIF|CONFID|UNCLAS|FOUO|RELTO|OFFICIAL|COMINT|ORCON", w):
                continue
            if re.fullmatch(r"[TSIUWVHCLO1]*REL|[TSIHUW]+", w):      # SIREL, TSISWIREL, SIISI ... (garbled banners)
                continue
            ocr_only = w not in self.caps_textlayer
            trusted = w in self.caps_textlayer_multi
            if any(_edit_distance(w, m) <= (1 if len(m) < 6 or (len(m) == 6 and trusted) else 2)
                   for m in K.marking_words):
                continue
            ratio = c / (c + self.other_n[w])
            if w in english:
                ok = ratio >= 0.97 and df >= 3 and self.other_n[w] <= 2
            else:
                ok = ratio >= 0.85
            # tokens seen only in OCR text are often misreadings; keep them only if they look like
            # typical compound codenames (two or more dictionary words run together)
            if ok and ocr_only:
                ok = _segments_into_words(w, english_short)
            if ok:
                found[w] = df
                if not trusted:
                    unsure.append(w)
        # tokens not seen on text-layer pages of two documents may be misreadings of a more common word
        for w in self._misreadings(unsure):
            del found[w]
        return found


# 'M. A. GENARO', 'G. CHAREST', 'Mr. SMITH', 'Sgt MOBLEY': initials or a personal honorific before an all-caps
# surname (not a role such as 'Chief' or 'Director', which comes before cryptonyms too)
INITIALS_SURNAME = re.compile(r"(?:(?:[A-Z]\.\s?){1,3}|(?i:mr|mrs|ms|miss|dr|sgt)\.?\s)([A-Z][A-Z'-]+)")


def surname_codenames(codenames, person_spans, min_docs=2):
    """Auto-detected codenames that NER finds as a surname in full names ('Walter E. FAUNTROY', 'CARL F.
    HANSSON', 'Manuel TELLO Troncoso', 'MANNARINO, SAM', 'M. A. GENARO') in at least min_docs documents:
    all-caps surnames in typed reports. person_spans yields (doc_id, span). The span must pass normalize_person,
    so titles, ranks and role words ('Chief QJWIN', 'Agent LITAMIL', 'Station LITAMIL', 'Project X'), numbered
    agent designations ('LITAMIL-3') and codenames in the given-name position don't count."""
    docs = collections.defaultdict(set)
    for doc_id, raw in person_spans:
        m = INITIALS_SURNAME.fullmatch(raw.strip())
        if m:
            if m.group(1) in codenames:
                docs[m.group(1)].add(doc_id)
            continue
        if "," in raw:                                 # 'MANNARINO, SAM' -> 'SAM MANNARINO'
            sur, given = raw.split(",", 1)
            raw = f"{(given.split() or [''])[0]} {(sur.split() or [''])[-1]}"
        name = normalize_person(raw, allcaps=True)
        if not name:
            continue
        toks = name.upper().split()
        if toks[0] not in codenames:
            for t in toks[1:]:
                if t in codenames:
                    docs[t].add(doc_id)
    return {w for w, d in docs.items() if len(d) >= min_docs}


# =========================================================================== identifiers

EMAIL_RE = re.compile(r"\b[A-Za-z0-9][A-Za-z0-9._%+\-]{0,63}@[A-Za-z0-9](?:[A-Za-z0-9\-]{0,62}\.)+[A-Za-z]{2,24}\b")
IBAN_RE = re.compile(r"\b([A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?)\b")
PHONE_RE = re.compile(r"(?<![\w+])\+\d[\d ().\-]{7,18}\d(?!\w)")


def _iban_ok(s):
    s = s.replace(" ", "")
    if not 15 <= len(s) <= 34:
        return False
    n = "".join(str(int(c, 36)) for c in s[4:] + s[:4])
    return int(n) % 97 == 1


def find_identifiers(text, kinds):
    out = []
    if "email" in kinds:
        out += [("Email address", m.group().lower().rstrip(".")) for m in EMAIL_RE.finditer(text)]
    if "iban" in kinds:
        out += [("Bank account (IBAN)", m.group(1).replace(" ", "")) for m in IBAN_RE.finditer(text) if _iban_ok(m.group(1))]
    if "phone" in kinds:
        for m in PHONE_RE.finditer(text):
            digits = re.sub(r"\D", "", m.group())
            if 9 <= len(digits) <= 15:
                out.append(("Phone number", "+" + digits))
    return out


# =========================================================================== NER (spaCy) with a per-page cache

def ner_key(model, text):
    return hashlib.sha1((model + "\0" + text).encode("utf-8", "replace")).hexdigest()


class NerCache:
    """data/<corpus>/ner_cache.db: page-text hash -> [[label, text], ...] for every entity spaCy found."""

    def __init__(self, path):
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE IF NOT EXISTS ner(h TEXT PRIMARY KEY, ents TEXT)")
        con.close()
        # connect again now that the file has content: on exFAT an empty file's inode number changes when it
        # gets its first data cluster, and SQLite, which checks that the file it opened is still at its path,
        # would refuse every later write ('attempt to write a readonly database', SQLITE_READONLY_DBMOVED)
        self.con = sqlite3.connect(path)

    def has(self, h):
        return self.con.execute("SELECT 1 FROM ner WHERE h=?", (h,)).fetchone() is not None

    def get(self, h):
        r = self.con.execute("SELECT ents FROM ner WHERE h=?", (h,)).fetchone()
        return json.loads(r[0]) if r else []

    def put_many(self, rows):
        self.con.executemany("INSERT OR REPLACE INTO ner VALUES(?,?)", rows)
        self.con.commit()


def run_ner(cache, texts_with_keys, model, n_process, total):
    """texts_with_keys yields (text, h) for pages missing from the cache."""
    import spacy
    nlp = spacy.load(model, exclude=["parser", "lemmatizer", "tagger", "attribute_ruler", "senter"])
    nlp.max_length = 2_000_000
    buf, done, t0 = [], 0, time.time()
    docs = nlp.pipe(texts_with_keys, as_tuples=True, batch_size=64, n_process=n_process)
    try:
        for doc, h in docs:
            buf.append((h, json.dumps([[e.label_, e.text] for e in doc.ents], ensure_ascii=False)))
            done += 1
            if len(buf) >= 2000:
                cache.put_many(buf)
                buf = []
                print(f"[ner] {done}/{total} pages  {done/max(time.time()-t0,1e-6):.0f}/s", flush=True)
        cache.put_many(buf)
    finally:
        # if this loop raises, the traceback keeps the generator alive and spaCy never tells its worker
        # processes to stop; they would wait for more text and keep the interpreter from exiting
        docs.close()


# =========================================================================== reading extracted documents

def iter_locators(extracted):
    """(sha1, relpath, file, byte offset or None) for every extracted document, in file-name order."""
    for fn in sorted(os.listdir(extracted)):
        path = os.path.join(extracted, fn)
        if fn.endswith(".json"):
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            yield d.get("sha1") or d["id"], d["relpath"], d["id"], path, None
        elif fn.endswith(".jsonl"):
            with open(path, "rb") as f:
                off = 0
                for line in f:
                    d = json.loads(line)
                    yield d.get("sha1") or d["id"], d["relpath"], d["id"], path, off
                    off += len(line)


def load_doc(path, off):
    if off is None:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    with open(path, "rb") as f:
        f.seek(off)
        return json.loads(f.readline())


def normalize_legacy(d):
    """Documents extracted by the pre-corpus version of extract.py."""
    if d["kind"] == "zip-pdf":
        d["kind"] = "pdf"
    if "src" not in d:
        srcs = d.get("sources") or []
        if d.get("member"):
            d["src"] = {"zip": srcs[0], "member": d["member"]}
        elif d["kind"] == "image-set":
            d["src"] = {"files": srcs}
        elif srcs:
            d["src"] = {"file": srcs[0]}
    return d


# =========================================================================== main build

SCHEMA = """
PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
CREATE TABLE documents(
    id TEXT PRIMARY KEY, relpath TEXT, filename TEXT, kind TEXT, title TEXT, collection TEXT, publisher TEXT,
    published TEXT, doc_date TEXT, date_source TEXT, year INTEGER, pages INTEGER, chars INTEGER, ocr_pages INTEGER,
    origin TEXT, classification TEXT, author TEXT, summary TEXT, sha1 TEXT, duplicates TEXT, sources TEXT,
    member TEXT, error TEXT, fields TEXT, src TEXT);
CREATE TABLE pages(rowid INTEGER PRIMARY KEY, doc_id TEXT, page_no INTEGER, text TEXT, ocr INTEGER);
CREATE VIRTUAL TABLE docs_fts USING fts5(id UNINDEXED, title, filename, author, tokenize="porter unicode61 remove_diacritics 2");
CREATE TABLE m_raw(key TEXT, doc_id TEXT, page_no INTEGER, count INTEGER, src INTEGER);
CREATE TABLE r_raw(src_key TEXT, dst_key TEXT, type TEXT, doc_id TEXT);
CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
"""
DOC_COLS = ["id", "relpath", "filename", "kind", "title", "collection", "publisher", "published", "doc_date",
            "date_source", "year", "pages", "chars", "ocr_pages", "origin", "classification", "author", "summary",
            "sha1", "duplicates", "sources", "member", "error", "fields", "src"]
# m_raw.src: 0 gazetteer/codename, 1 NER/pattern hit on a known entity, 2 NER/pattern candidate,
#            3 theme, 4 structured metadata
KNOWN, CANDIDATE, STRUCT = 1, 2, 4


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--no-ner", "--no-spacy", dest="no_ner", action="store_true")
    ap.add_argument("--processes", type=int, default=None)
    args = ap.parse_args()
    C = load_corpus(args.corpus)
    K = packs.load(C.packs, C.index["keep_aliases"])
    K.add_origin_rules(C.metadata["origin_rules"])
    K.suppress_aliases(C.index["suppress_aliases"])
    I, MD = C.index, C.metadata
    if args.no_ner:
        I["ner"] = False
    t0 = time.time()
    if not os.path.isdir(C.extracted_dir):
        raise SystemExit(f"[{C.id}] nothing extracted yet: run build/extract.py --corpus {C.id}")
    print(f"[{C.id}] packs: {' -> '.join(K.packs)} ({len(K.entities)} curated entities, {len(K.ideas)} themes)", flush=True)

    strip = K.strip_patterns

    def clean(text):
        for p in strip:
            text = p.sub(" ", text)
        return text

    caps_mode = I["allcaps_matching"] == "auto"

    # ---------------------------------------------------------------- pass 1: dedupe
    by_sha = collections.defaultdict(list)
    n_docs = 0
    for sha, relpath, did, path, off in iter_locators(C.extracted_dir):
        by_sha[sha].append((relpath, did, path, off))
        n_docs += 1
    prefer = tuple(MD["dedupe_prefer"])
    unique = []
    for group in by_sha.values():
        group.sort(key=lambda g: ("!/" in g[0], not (prefer and g[0].startswith(prefer)), len(g[0])))
        unique.append((group[0], [g[0] for g in group[1:]]))
    unique.sort(key=lambda u: u[0][0].lower())
    del by_sha
    print(f"[load] {n_docs} extracted, {len(unique)} unique ({n_docs-len(unique)} duplicates folded)", flush=True)

    tmp = C.db_path + ".tmp"
    os.makedirs(C.data_dir, exist_ok=True)
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)

    # ---------------------------------------------------------------- entity registry
    entities = {}                      # key -> {key, name, type, description, aliases, auto, source}
    matcher = Matcher()
    known_upper = set()
    for key, e in K.entities.items():
        entities[key] = dict(key=key, name=e["name"], type=e["type"], description=e["description"],
                             aliases=list(e["aliases"]), auto=0, source="gazetteer")
        for a in set(e["aliases"]):
            matcher.add(a, key, e["type"])
            for tok in tokenize(a):
                if tok.isupper():
                    known_upper.add(tok)
    person_alias = {}
    alias_any = {}                     # plain(alias) -> key, any type (for NER orgs/places, structured refs)
    for e in entities.values():
        for a in e["aliases"]:
            alias_any.setdefault((e["type"], plain(a)), e["key"])
            if e["type"] == "person":
                n = normalize_person(a) or a
                person_alias[plain(n)] = e["key"]
                person_alias[plain(a)] = e["key"]
    addr_alias = {}                    # email address -> entity key (from headers)

    def resolve(ref):
        """Entity ref from structured metadata -> key (creating the entity if needed)."""
        t, name = ref["type"], norm_ws(ref["name"])
        key = ref.get("key")
        if not key:
            if t == "person":
                key = person_alias.get(plain(normalize_person(name) or name)) or f"person:{name}"
            elif t == "identifier":
                name = name.lower() if "@" in name else name
                key = addr_alias.get(name) or f"identifier:{name}"
            else:
                key = alias_any.get((t, plain(name))) or f"{t}:{name}"
        e = entities.get(key)
        if e is None:
            e = entities[key] = dict(key=key, name=name, type=t, description=ref.get("description", ""),
                                     aliases=[name], auto=0, source=ref.get("source", "metadata"))
        for a in ref.get("aliases", []):
            if a and a not in e["aliases"]:
                e["aliases"].append(a)
            if "@" in a:
                addr_alias.setdefault(a.lower(), key)
        return key

    # ---------------------------------------------------------------- pass 2: metadata, pages, structured entities
    codes = CodenameStats(known_upper) if I["codenames"] else None
    year_of = {}
    n_pages = n_chars = 0
    doc_batch, page_batch, m_batch, r_batch = [], [], [], []

    def flush():
        if doc_batch:
            con.executemany(f"INSERT INTO documents({','.join(DOC_COLS)}) VALUES({','.join('?'*len(DOC_COLS))})",
                            [tuple(r[c] for c in DOC_COLS) for r in doc_batch])
            con.executemany("INSERT INTO docs_fts(id,title,filename,author) VALUES(?,?,?,?)",
                            [(r["id"], r["title"], r["filename"], r["author"]) for r in doc_batch])
        con.executemany("INSERT INTO pages(doc_id,page_no,text,ocr) VALUES(?,?,?,?)", page_batch)
        con.executemany("INSERT INTO m_raw VALUES(?,?,?,?,?)", m_batch)
        con.executemany("INSERT INTO r_raw VALUES(?,?,?,?)", r_batch)
        for b in (doc_batch, page_batch, m_batch, r_batch):
            b.clear()

    for (relpath, did, path, off), dups in unique:
        d = normalize_legacy(load_doc(path, off))
        pages = d.get("pages", [])
        full = "\n".join(p["text"] for p in pages)
        first = "\n".join(p["text"] for p in pages[:2])
        meta = dict(d.get("meta") or {})
        meta["fields"] = dict(d.get("fields") or {})
        meta["entities"] = list(d.get("entities") or [])
        meta["relations"] = list(d.get("relations") or [])
        for hook in K.metadata:
            hook(d, full, meta, C)
        date, src = meta.get("date") or "", meta.get("date_source") or ""
        if not date:
            date = date_from_filename(file_part(d), C)
            src = "filename" if date else ""
        if not date:
            date, src = date_from_text(full, d["relpath"], C, K)
        year = int(date[:4]) if date[:4].isdigit() else None
        cleaned_first = norm_ws(clean(first))
        if d.get("attachments"):
            meta["fields"].setdefault("Attachments read", ", ".join(d["attachments"]))
        row = dict(
            id=d["id"], relpath=d["relpath"], filename=os.path.basename(file_part(d)), kind=d["kind"],
            title=meta.get("title") or make_title(d, first, MD["title_strip"]),
            collection=d.get("collection") or meta.get("collection") or collection_of(file_part(d), MD),
            publisher=meta.get("publisher") or publisher_of(d["relpath"], MD["publishers"]),
            published=next((p for p in (fn(d["relpath"]) for fn in K.published_date) if p), ""),
            doc_date=date, date_source=src, year=year,
            pages=len(pages), chars=len(full), ocr_pages=sum(1 for p in pages if p.get("ocr")),
            origin=meta.get("origin") or origin_of(full, d["relpath"], d["kind"], C, K),
            classification=meta.get("classification") or classification_of(full, K),
            author=meta.get("author") or (author_line(first) if d["kind"] == "pdf" else ""),
            summary=cleaned_first[:600], sha1=d.get("sha1", ""),
            duplicates=json.dumps(dups), sources=json.dumps(d.get("sources", [])),
            member=d.get("member", ""), error=d.get("error", ""),
            fields=json.dumps(meta["fields"], ensure_ascii=False) if meta["fields"] else "",
            src=json.dumps(d.get("src") or {}),
        )
        doc_batch.append(row)
        year_of[d["id"]] = year
        for p in pages:
            page_batch.append((d["id"], p["n"], p["text"], int(bool(p.get("ocr")))))
            n_chars += len(p["text"])
            if codes is not None:
                ct = clean(p["text"])
                if caps_mode and is_allcaps(ct):
                    codes.add_allcaps(ct)
                else:
                    codes.add(d["id"], ct, bool(p.get("ocr")))
        n_pages += len(pages)
        seen = set()
        for ref in meta["entities"]:
            k = resolve(ref)
            if k not in seen:
                seen.add(k)
                m_batch.append((k, d["id"], 1, 1, STRUCT))
        for a, rtype, b in meta["relations"]:
            r_batch.append((resolve(a), resolve(b), rtype, d["id"]))
        if len(page_batch) > 5000 or len(doc_batch) > 2000:
            flush()
    flush()
    con.commit()
    n_docs = len(year_of)
    print(f"[meta] {n_docs} docs, {n_pages} pages, {n_chars/1e6:.1f}M chars, "
          f"{sum(1 for e in entities.values() if e['source'] == 'metadata')} entities from structured metadata "
          f"({time.time()-t0:.0f}s)", flush=True)

    # ---------------------------------------------------------------- codenames
    codenames = {}
    if codes is not None:
        codenames = codes.detect(K)
        del codes

    # ---------------------------------------------------------------- NER (cached per page)
    ner_on = I["ner"]
    labels = set(I["ner_labels"])
    model = I["ner_model"]
    cache = None
    if ner_on:
        import importlib.util
        if importlib.util.find_spec("spacy") is None:
            print("[ner] spaCy is not installed; skipping NER (pip install spacy && python -m spacy download "
                  f"{model})", flush=True)
            ner_on = False
        elif importlib.util.find_spec(model) is None:
            print(f"[ner] spaCy model {model} is not installed; skipping NER (python -m spacy download {model})", flush=True)
            ner_on = False
    if ner_on:
        cache = NerCache(os.path.join(C.data_dir, "ner_cache.db"))
        # each page's cache key, computed once (cleaning and hashing every page is a pass of its own)
        con.execute("CREATE TABLE page_ner(rowid INTEGER PRIMARY KEY, h TEXT)")
        batch = []
        for rowid, text in con.execute("SELECT rowid, text FROM pages ORDER BY rowid"):
            batch.append((rowid, ner_key(model, norm_ws(clean(text))[:200000])))
            if len(batch) >= 5000:
                con.executemany("INSERT INTO page_ner VALUES(?,?)", batch)
                batch.clear()
        con.executemany("INSERT INTO page_ner VALUES(?,?)", batch)
        con.commit()
        want = {h for (h,) in con.execute("SELECT DISTINCT h FROM page_ner") if not cache.has(h)}
        if want:
            print(f"[ner] {len(want)} pages to analyse with {model} (cached pages are reused)", flush=True)

            def gen():
                for text, h in con.execute("SELECT p.text, n.h FROM pages p JOIN page_ner n ON n.rowid = p.rowid "
                                           "ORDER BY p.rowid"):
                    if h in want:
                        want.discard(h)
                        yield norm_ws(clean(text))[:200000], h
            run_ner(cache, gen(), model, args.processes or I["processes"] or max(1, (os.cpu_count() or 4) - 2), len(want))
        else:
            print("[ner] all pages cached", flush=True)

    # codenames become entities only now, once NER has had its say about which of them are surnames
    surnames = set()
    if codenames and ner_on:
        def person_spans():
            for doc_id, h in con.execute("SELECT p.doc_id, n.h FROM page_ner n JOIN pages p ON p.rowid = n.rowid"):
                for label, raw in cache.get(h):
                    if label in ("PERSON", "PER"):
                        yield doc_id, raw
        surnames = surname_codenames(codenames, person_spans())
        for w in surnames:
            del codenames[w]
        if surnames:
            print(f"[codenames] {len(surnames)} set aside as surnames (NER found them in full names)", flush=True)
    for w in codenames:
        key = f"program:{w}"
        if key in entities:
            continue
        entities[key] = dict(key=key, name=w, type="program", description="Codename auto-detected from the documents.",
                             aliases=[w], auto=1, source="codename")
        matcher.add(w, key, "program")
    if codenames:
        print(f"[codenames] {len(codenames)} auto-detected", flush=True)

    # ---------------------------------------------------------------- pass 3: mentions
    idea_res = []
    for name, pats, desc in K.ideas:
        key = f"idea:{name}"
        entities.setdefault(key, dict(key=key, name=name, type="idea", description=desc, aliases=[name], auto=0, source="theme"))
        # "(?i:...)" alternatives go into one re.I regex: scoped flags defeat the regex engine's
        # optimisations and made theme matching ~2x slower
        ci = [p[4:-1] for p in pats if p.startswith("(?i:") and p.endswith(")")]
        cs = [p for p in pats if not (p.startswith("(?i:") and p.endswith(")"))]
        normal = ([re.compile("|".join(ci), re.I)] if ci else []) + ([re.compile("|".join(cs))] if cs else [])
        idea_res.append((key, normal, [re.compile("|".join(ci + cs), re.I)]))
    candidates = {}                    # key -> entity dict, kept if seen in enough documents
    id_kinds = set(I["identifiers"])
    m_batch = []
    t3 = time.time()

    def finish_doc(doc_id, idea_pages):
        totals = collections.Counter()
        for (key, _), c in idea_pages.items():
            totals[key] += c
        for (key, page_no), c in idea_pages.items():
            if totals[key] >= K.min_idea_hits:
                m_batch.append((key, doc_id, page_no, c, 3))

    # all-caps tokens that are never a surname, so "Miami JMWAVE" or "John Smith SUBJECT" is no person
    caps_stop = known_upper | set(codenames) | K.codename_stop | set(K.marking_words)
    cur_doc, idea_pages = None, collections.Counter()
    n_done = 0
    pages_sql = ("SELECT p.doc_id, p.page_no, p.text, n.h FROM pages p JOIN page_ner n ON n.rowid = p.rowid ORDER BY p.rowid"
                 if ner_on else "SELECT doc_id, page_no, text, NULL FROM pages ORDER BY rowid")
    for doc_id, page_no, text, h in con.execute(pages_sql):
        if doc_id != cur_doc:
            if cur_doc is not None:
                finish_doc(cur_doc, idea_pages)
            cur_doc, idea_pages = doc_id, collections.Counter()
            n_done += 1
            if n_done % 20000 == 0:
                print(f"[mentions] {n_done}/{n_docs} docs  {time.time()-t3:.0f}s", flush=True)
        cleaned = clean(text)
        caps = caps_mode and is_allcaps(cleaned)
        gaz = collections.Counter(matcher.find(tokenize(cleaned), caps))
        for key, c in gaz.items():
            m_batch.append((key, doc_id, page_no, c, 0))
        extra = collections.Counter()       # NER / pattern hits on this page
        if ner_on:
            ents = cache.get(h)
            for label, raw in ents:
                if label not in labels:
                    continue
                if label in ("PERSON", "PER"):
                    n = normalize_person(raw, caps_stop)
                    if not n:
                        continue
                    key = person_alias.get(plain(n))
                    if key is None:
                        # don't let codenames masquerade as people when NER saw them in title case ("Miami Jmwave")
                        if any(tok.upper() in codenames for tok in n.split()):
                            continue
                        key = f"person:{n}"
                        if key not in entities and key not in candidates:
                            candidates[key] = dict(key=key, name=n, type="person", description="Name detected by NER (unverified).",
                                                   aliases=[n], auto=1, source="ner")
                elif label in ("ORG", "GPE", "LOC"):
                    span = tidy_org(raw)               # known names first: "Shell" is fine if a pack defines it
                    p0 = plain(span)
                    key = (alias_any.get(("place" if label != "ORG" else "organization", p0)) or alias_any.get(("agency", p0))
                           or alias_any.get(("company", p0)) or alias_any.get(("organization", p0)) or alias_any.get(("place", p0)))
                    n = span if key else normalize_org(raw)
                    if not n or (n.isupper() and (n in codenames or n in surnames)):
                        continue
                    t = "place" if label in ("GPE", "LOC") else ("company" if looks_like_company(n) else "organization")
                    if key is None:
                        key = f"{t}:{n}"
                        if key not in entities and key not in candidates:
                            candidates[key] = dict(key=key, name=n, type=t, description=f"{'Place' if t == 'place' else 'Organization'} detected by NER (unverified).",
                                                   aliases=[n], auto=1, source="ner")
                else:
                    continue
                extra[key] += 1
        if id_kinds:
            for desc, value in find_identifiers(text, id_kinds):
                key = addr_alias.get(value) or f"identifier:{value}"
                if key not in entities and key not in candidates:
                    candidates[key] = dict(key=key, name=value, type="identifier", description=desc, aliases=[value],
                                           auto=1, source="pattern")
                extra[key] += 1
        for key, c in extra.items():
            if key in entities:
                if key not in gaz:
                    m_batch.append((key, doc_id, page_no, c, KNOWN))
            else:
                m_batch.append((key, doc_id, page_no, c, CANDIDATE))
        for key, rx_normal, rx_caps in idea_res:
            c = sum(len(rx.findall(cleaned)) for rx in (rx_caps if caps else rx_normal))
            if c:
                idea_pages[(key, page_no)] = c
        if len(m_batch) > 20000:
            con.executemany("INSERT INTO m_raw VALUES(?,?,?,?,?)", m_batch)
            m_batch.clear()
    if cur_doc is not None:
        finish_doc(cur_doc, idea_pages)
    con.executemany("INSERT INTO m_raw VALUES(?,?,?,?,?)", m_batch)
    con.commit()
    print(f"[mentions] done in {time.time()-t3:.0f}s", flush=True)

    # ---------------------------------------------------------------- keep candidates seen in enough documents
    con.execute("CREATE INDEX m_raw_key ON m_raw(key)")
    kept = 0
    for key, n_docs_k, all_ocr in con.execute("""
            SELECT m.key, COUNT(DISTINCT m.doc_id), MIN(p.ocr) FROM m_raw m
            JOIN pages p ON p.doc_id = m.doc_id AND p.page_no = m.page_no
            WHERE m.src = 2 GROUP BY m.key"""):
        e = candidates.get(key)
        if e is None or key in entities:
            continue
        need = I["identifier_min_docs"] if e["type"] == "identifier" else I["ner_min_docs"]
        if n_docs_k < need:
            continue
        if e["type"] == "person" and all_ocr and e["name"].split()[0] not in DICT_WORDS:
            continue   # OCR-only "names" like "Apps Servers" need a recognisable given name
        entities[key] = e
        kept += 1
    del candidates
    print(f"[ner] {kept} additional entities from NER / patterns", flush=True)

    # ---------------------------------------------------------------- entity ids, mentions
    # one row per (entity, document, page); structured mentions count once unless the text also matched
    con.execute("""CREATE TABLE m_agg AS SELECT key, doc_id, page_no,
                          MAX(SUM(CASE WHEN src=4 THEN 0 ELSE count END), 1) AS c
                   FROM m_raw GROUP BY key, doc_id, page_no""")
    stats = {}
    for key, nd, nm in con.execute("SELECT key, COUNT(DISTINCT doc_id), SUM(c) FROM m_agg GROUP BY key"):
        if key in entities:
            stats[key] = (nd, nm)
    keys = sorted(stats, key=lambda k: (-stats[k][0], k))
    eid = {k: i + 1 for i, k in enumerate(keys)}
    con.executescript("""
    CREATE TABLE entities(id INTEGER PRIMARY KEY, key TEXT UNIQUE, name TEXT, type TEXT, description TEXT,
        aliases TEXT, auto INTEGER, doc_count INTEGER, mention_count INTEGER, first_year INTEGER, last_year INTEGER,
        source TEXT);
    CREATE TABLE keymap(key TEXT PRIMARY KEY, id INTEGER);
    CREATE TABLE mentions(entity_id INTEGER, doc_id TEXT, page_no INTEGER, count INTEGER);
    CREATE TABLE edges(src INTEGER, dst INTEGER, docs INTEGER, npmi REAL);
    CREATE TABLE relations(src INTEGER, dst INTEGER, type TEXT, docs INTEGER, first_date TEXT, last_date TEXT);
    CREATE TABLE relation_docs(src INTEGER, dst INTEGER, type TEXT, doc_id TEXT);
    """)
    con.executemany("INSERT INTO keymap VALUES(?,?)", eid.items())
    con.execute("INSERT INTO mentions SELECT k.id, m.doc_id, m.page_no, m.c FROM m_agg m JOIN keymap k ON k.key = m.key")
    years = collections.defaultdict(list)
    for e_id, lo, hi in con.execute("""SELECT m.entity_id, MIN(d.year), MAX(d.year) FROM mentions m
                                       JOIN documents d ON d.id = m.doc_id WHERE d.year IS NOT NULL GROUP BY m.entity_id"""):
        years[e_id] = (lo, hi)
    ent_rows = []
    for k in keys:
        e = entities[k]
        lo, hi = years.get(eid[k], (None, None))
        ent_rows.append((eid[k], k, e["name"], e["type"], e["description"], json.dumps(sorted(set(e["aliases"]))), e["auto"],
                         stats[k][0], stats[k][1], lo, hi, e["source"]))
    con.executemany("INSERT INTO entities VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", ent_rows)
    con.execute("CREATE INDEX mentions_ent ON mentions(entity_id)")
    con.execute("CREATE INDEX mentions_doc ON mentions(doc_id)")

    # ---------------------------------------------------------------- co-occurrence
    window, min_edge, max_ents = I["window"], I["min_edge_docs"], I["max_window_entities"]
    pair_docs = collections.Counter()      # (a, b) -> number of documents where they co-occur
    cur_doc, units = None, collections.defaultdict(set)
    crowded = [0]

    def close_doc():
        pairs = set()
        for ents in units.values():
            if len(ents) > max_ents:       # registry hubs / huge tables: pairs would explode and mean little
                crowded[0] += 1
                continue
            ents = sorted(ents)
            for i in range(len(ents)):
                a = ents[i]
                pairs.update((a, b) for b in ents[i + 1:])
        pair_docs.update(pairs)

    for e_id, doc_id, page_no in con.execute("SELECT entity_id, doc_id, page_no FROM mentions ORDER BY doc_id"):
        if doc_id != cur_doc:
            if cur_doc is not None:
                close_doc()
            cur_doc, units = doc_id, collections.defaultdict(set)
        units[(page_no - 1) // window].add(e_id)
    if cur_doc is not None:
        close_doc()
    N = n_docs
    df = {eid[k]: stats[k][0] for k in keys}
    edges = []
    for (a, b), n_ab in pair_docs.items():
        if n_ab < min_edge:
            continue
        p_ab, p_a, p_b = n_ab / N, df[a] / N, df[b] / N
        pmi = math.log(p_ab / (p_a * p_b))
        npmi = pmi / -math.log(p_ab) if p_ab < 1 else 1.0
        edges.append((a, b, n_ab, round(npmi, 4)))
    pair_docs.clear()
    if crowded[0]:
        print(f"[graph] {crowded[0]} page windows with more than {max_ents} entities left out of co-occurrence", flush=True)
    con.executemany("INSERT INTO edges VALUES(?,?,?,?)", edges)
    con.execute("CREATE INDEX edges_src ON edges(src)")
    con.execute("CREATE INDEX edges_dst ON edges(dst)")

    # ---------------------------------------------------------------- typed relations
    con.execute("""INSERT INTO relation_docs SELECT DISTINCT a.id, b.id, r.type, r.doc_id FROM r_raw r
                   JOIN keymap a ON a.key = r.src_key JOIN keymap b ON b.key = r.dst_key WHERE a.id != b.id""")
    con.execute("""INSERT INTO relations SELECT x.src, x.dst, x.type, COUNT(DISTINCT x.doc_id), MIN(d.doc_date), MAX(d.doc_date)
                   FROM relation_docs x JOIN documents d ON d.id = x.doc_id GROUP BY x.src, x.dst, x.type""")
    n_rel = con.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
    con.execute("CREATE INDEX relations_src ON relations(src)")
    con.execute("CREATE INDEX relations_dst ON relations(dst)")
    con.execute("CREATE INDEX relation_docs_pair ON relation_docs(src, dst)")
    print(f"[graph] {len(keys)} entities, {len(edges)} edges (>= {min_edge} shared docs), {n_rel} typed relations", flush=True)

    # ---------------------------------------------------------------- finish
    con.executescript("""
    DROP TABLE m_raw; DROP TABLE m_agg; DROP TABLE r_raw; DROP TABLE keymap; DROP TABLE IF EXISTS page_ner;
    CREATE INDEX pages_doc ON pages(doc_id, page_no);
    CREATE VIRTUAL TABLE pages_fts USING fts5(text, content='pages', content_rowid='rowid',
        tokenize="porter unicode61 remove_diacritics 2");
    INSERT INTO pages_fts(pages_fts) VALUES('rebuild');
    """)
    con.executemany("INSERT INTO meta VALUES(?,?)", [
        ("built", time.strftime("%Y-%m-%d %H:%M:%S")), ("documents", str(n_docs)), ("pages", str(n_pages)),
        ("archive", C.root or ""), ("corpus", C.id), ("title", C.title), ("packs", ",".join(K.packs)),
        ("ner", ",".join(sorted(labels)) if ner_on else "off")])
    con.commit()
    con.execute("VACUUM")
    con.close()
    os.replace(tmp, C.db_path)
    print(f"[done] {C.db_path} in {(time.time()-t0)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
