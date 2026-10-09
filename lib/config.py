"""
Corpus configuration.

Every dataset ("corpus") is described by one TOML file in corpora/<id>.toml. The
file names the folder to index, which files to include, which knowledge packs
(lib/packs/*) to apply, and how to read metadata. Everything has a default, so a
minimal config is just:

    title = "My leak"
    root  = "/path/to/files"

See corpora/_template.toml for every option. Files whose name starts with "_" are
templates and are never listed as corpora.
"""
import copy
import datetime
import fnmatch
import os
import re
import tomllib

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPORA_DIR = os.environ.get("NEWSROOM_CORPORA", os.path.join(PROJECT, "corpora"))
DATA_ROOT = os.environ.get("NEWSROOM_DATA", os.path.join(PROJECT, "data"))

DOCUMENT_FORMATS = ["pdf", "image", "html", "text", "email", "mbox", "msg", "docx", "pptx", "xlsx",
                    "odf", "rtf", "doc", "xls", "csv"]

DEFAULTS = {
    "title": None,                 # defaults to the corpus id
    "description": "",
    "root": None,                  # folder holding the files (absolute, ~ or $VARS allowed, or relative to the project)
    "include": [],                 # glob patterns on paths relative to root; empty = everything
    "exclude": [],                 # glob patterns; a matching folder is skipped entirely
    "packs": ["core"],             # knowledge packs, see lib/packs/
    "findings": None,              # optional Markdown report served at /findings (relative to the project)
    "data_dir": None,              # defaults to data/<id>
    "dates": {
        "min_year": 1900,          # any date outside [min_year, max_year] is ignored
        "max_year": None,          # defaults to the current year
        "text_min_year": None,     # bounds for "first date found in the text" (defaults to min/max_year)
        "text_max_year": None,
        "chart_min_year": None,    # x-axis range for year charts (defaults to the data)
        "chart_max_year": None,
        "declassify_min_year": None,   # bounds for the "Declassify On minus 25 years" estimate
        "declassify_max_year": None,
        "two_digit_century": 1900, # how to read 2-digit years in structured headers (NARA forms, cables)
    },
    "extract": {
        "formats": list(DOCUMENT_FORMATS),
        "ocr": True,
        "ocr_lang": "eng",         # Tesseract language(s), e.g. "eng+rus" (install the traineddata first)
        "ocr_min_chars": 200,      # PDF pages with less text-layer text than this are OCR'd
        "min_image_kb": 15,        # skip icons / spacer images
        "page_scan_pattern": "",   # regex grouping single-page scans into one document (named groups base, n)
        "max_file_mb": 1024,       # skip files bigger than this (archives and record files are exempt)
        "max_member_mb": 256,      # skip archive members / attachments bigger than this
        "archives": ["zip"],       # also: "tar" (tar/tgz/tbz2/txz), "7z", "rar" (read with bsdtar)
        "archive_members": [],     # formats read from inside archives; empty = all formats above
        "text_page_chars": 12000,  # split long text/office documents into pseudo-pages of about this size
        "sheet_page_rows": 200,    # rows per page for spreadsheets and CSV tables
        "max_sheet_rows": 50000,   # rows read per sheet / CSV table
        "email_attachments": True, # extract text from email attachments (as extra pages)
        "html_extensionless": True,  # sniff extension-less files for HTML
        "sidecar": "",             # "ia-hocr": use Internet Archive OCR files saved next to PDFs instead of Tesseract
        "encoding_fallback": "utf-8",  # for text that is not UTF-8: "cp1252" (Western), "cp1251" (Russian), "cp1255" (Hebrew) ...
    },
    "index": {
        "ner": True,               # spaCy named-entity recognition
        "ner_model": "en_core_web_sm",
        "ner_labels": ["PERSON"],  # also: "ORG", "GPE", "LOC"
        "ner_min_docs": 2,         # an NER name needs this many documents to become an entity
        "codenames": True,         # auto-detect ALL-CAPS codenames (intelligence / military material)
        "suppress_aliases": [],    # pack-defined names that must not match in this corpus, e.g. ["SEC", "BP"]
        "keep_aliases": [],        # names a pack's SUPPRESS_ALIASES turns off that should match here, e.g. ["ETA"]
        "allcaps_matching": "auto",  # "auto": match names case-insensitively on ALL-CAPS pages (telegrams, cables); "off"
        "identifiers": [],         # pattern entities: "email", "iban", "phone"
        "identifier_min_docs": 2,
        "window": 5,               # pages per co-occurrence window
        "max_window_entities": 400,  # windows with more entities than this add no co-occurrence pairs
        "min_edge_docs": 2,
        "processes": None,         # NER worker processes (default: cores - 2)
    },
    "metadata": {
        "collection_depth": 1,     # how many folder levels name a collection
        "collection_aliases": {},  # folder name -> collection label
        "publishers": [],          # [[regex on path, publisher name], ...]
        "origin_rules": [],        # [{pattern, label, priority, target = "head" | "path", unless}]
        "html_origin": "Web page",
        "default_origin": "Other / unknown",
        "dedupe_prefer": [],       # path prefixes preferred when identical files are folded together
        "title_strip": r"^\d{4}-\d{2}-\d{2}_?",   # regex removed from file names before they become titles
    },
    "ui": {
        "search_examples": [],
        "hide_hubs": 800,          # default "hide hubs over N documents" in the network view
        "hub_hint": "",
        "timeline_presets": [],    # [[label, "Name A|Name B|..."], ...]
        "year_note": "",
    },
    "records": [],                 # structured adapters, e.g. CSV with one record per row, ICIJ Offshore Leaks
}


class Corpus:
    """A loaded corpus config. Sections are plain dicts; paths are resolved."""

    def __init__(self, cid, raw, path=None):
        self.id = cid
        self.path = path
        cfg = _merge(copy.deepcopy(DEFAULTS), raw)
        self.raw = cfg
        self.title = cfg["title"] or cid
        self.description = cfg["description"]
        self.root = _resolve(cfg["root"]) if cfg["root"] else None
        self.include = list(cfg["include"])
        self.exclude = list(cfg["exclude"])
        self.packs = list(cfg["packs"])
        self.findings = _resolve(cfg["findings"]) if cfg["findings"] else None
        self.data_dir = _resolve(cfg["data_dir"]) if cfg["data_dir"] else os.path.join(DATA_ROOT, cid)
        self.dates = cfg["dates"]
        d = self.dates
        d["max_year"] = d["max_year"] or datetime.date.today().year
        for k in ("text_min_year", "declassify_min_year"):
            d[k] = d[k] or d["min_year"]
        for k in ("text_max_year", "declassify_max_year"):
            d[k] = d[k] or d["max_year"]
        self.extract = cfg["extract"]
        self.extract["archive_members"] = self.extract["archive_members"] or list(self.extract["formats"])
        self.index = cfg["index"]
        self.metadata = cfg["metadata"]
        self.ui = cfg["ui"]
        self.records = cfg["records"]
        project = os.path.realpath(PROJECT)
        if self.root and (project + os.sep).startswith(os.path.realpath(self.root) + os.sep):
            # never index this project (code, caches, indexes) if it lives inside the archive
            self.exclude.append(os.path.relpath(project, os.path.realpath(self.root)).replace(os.sep, "/"))

    # ---- paths
    @property
    def extracted_dir(self):
        return os.path.join(self.data_dir, "extracted")

    @property
    def ocr_dir(self):
        return os.path.join(self.data_dir, "ocr")

    @property
    def staged_dir(self):
        return os.path.join(self.data_dir, "staged")

    @property
    def db_path(self):
        return os.path.join(self.data_dir, "index.db")

    def exists(self):
        return os.path.exists(self.db_path)

    # ---- include / exclude
    def excluded_dir(self, rel):
        rel = rel.replace(os.sep, "/")
        return any(_dir_match(rel, p) for p in self.exclude)

    def could_contain(self, rel_dir):
        """False when no include pattern can match anything inside this folder (so the walk can skip it).
        A glob can only match paths that start with its literal prefix (the part before * ? or [)."""
        if not self.include:
            return True
        d = rel_dir.replace(os.sep, "/") + "/"
        for p in self.include:
            m = re.search(r"[*?\[]", p)
            head = p[:m.start()] if m else p
            if d.startswith(head) or head.startswith(d):
                return True
        return False

    def wanted_file(self, rel):
        rel = rel.replace(os.sep, "/")
        if any(fnmatch.fnmatchcase(rel, p) or _dir_match(rel, p) for p in self.exclude):
            return False
        return not self.include or any(fnmatch.fnmatchcase(rel, p) or _dir_match(rel, p) for p in self.include)

    def __repr__(self):
        return f"<Corpus {self.id} root={self.root!r} packs={self.packs}>"


def _dir_match(rel, pat):
    """'claude', 'claude/' and 'claude/**' all mean the folder claude and everything in it."""
    p = re.sub(r"/(\*\*)?$", "", pat)
    return rel == p or rel.startswith(p + "/") or fnmatch.fnmatchcase(rel, p)


def _merge(base, over):
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def _resolve(p):
    p = os.path.expandvars(os.path.expanduser(p))
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(PROJECT, p))


def corpus_files():
    if not os.path.isdir(CORPORA_DIR):
        return []
    return sorted(f for f in os.listdir(CORPORA_DIR) if f.endswith(".toml") and not f.startswith(("_", ".")))


def load_corpus(name_or_path):
    """Load corpora/<name>.toml (or an explicit path to a .toml file)."""
    path = name_or_path
    if not path.endswith(".toml"):
        path = os.path.join(CORPORA_DIR, name_or_path + ".toml")
    if not os.path.exists(path):
        known = ", ".join(f[:-5] for f in corpus_files()) or "(none)"
        raise SystemExit(f"Unknown corpus {name_or_path!r}. Known corpora: {known}")
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    cid = raw.pop("id", None) or os.path.basename(path)[:-5]
    return Corpus(cid, raw, path)


def list_corpora():
    out = []
    for f in corpus_files():
        try:
            out.append(load_corpus(f[:-5]))
        except Exception as e:  # a broken config should not take the app down
            print(f"[config] skipping {f}: {e}")
    return out
