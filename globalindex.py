"""
Cross-corpus entity index for the app's global views (/all/...): data/global.db.

Entities from every built corpus are merged by type and name, ignoring case and the accents of Latin
letters ('person:José García' = 'person:Jose Garcia'); letters of other scripts are kept as they are.
The file holds the merged entities, which corpus entity keys belong to each, and per-corpus document
counts per year. Spelling variants that fold to one entity within a corpus ('MOSSACK FONSECA & CO',
'Mossack Fonseca & Co') count each document once. Co-occurrence links, mentions and documents stay in
the corpus indexes and are read from there at request time.

The index rebuilds itself when a corpus index is added, rebuilt or removed, or a corpus's title or year
settings change: open_current() compares them with the ones the global index was built from. A stale
global index keeps being served while the new one builds in a background thread; only the very first
build makes a request wait, and only if it asks to.
"""
import json
import os
import sqlite3
import threading
import time
import traceback
import unicodedata
import urllib.parse

from lib import config

_lock = threading.Lock()
_state = {"thread": None, "failed": None}      # failed: (stamp, time) of the last failed build


def path():
    return os.path.join(config.DATA_ROOT, "global.db")


def gkey(etype, name):
    """The global identity of an entity: its type and folded name. Case and spacing are ignored, and so are
    accents on Latin letters ('José' = 'Jose'); other scripts keep every letter and mark ('Банк', 'й')."""
    out, base = [], ""
    for ch in unicodedata.normalize("NFKD", name or ""):
        if unicodedata.combining(ch):
            if base and ord(base) < 0x250:
                continue
        else:
            base = ch
        out.append(ch)
    folded = unicodedata.normalize("NFC", "".join(out)).casefold()
    return f"{etype}:{' '.join(folded.split())}"


def year_range(c, con):
    """Year range for a corpus's charts: its config, else its dated documents (ignoring stray outliers)."""
    d = c.dates
    lo, hi = d.get("chart_min_year"), d.get("chart_max_year")
    if not (lo and hi):
        r = con.execute("SELECT MIN(year), MAX(year) FROM documents WHERE year BETWEEN ? AND ?",
                        (d["min_year"], d["max_year"])).fetchone()
        lo, hi = lo or r[0] or d["min_year"], hi or r[1] or d["max_year"]
    return lo, hi


def _stamp(corpora):
    """What the global index depends on: each corpus index file and the config values copied into it."""
    out = []
    for c in sorted(corpora, key=lambda c: c.id):
        try:
            st = os.stat(c.db_path)
        except OSError:
            continue
        d = c.dates
        out.append([c.id, st.st_size, int(st.st_mtime), c.title,
                    d.get("min_year"), d.get("max_year"), d.get("chart_min_year"), d.get("chart_max_year")])
    return json.dumps(out)


def _uri(p, mode=None):
    return "file:" + urllib.parse.quote(p) + (f"?mode={mode}" if mode else "")


def _open():
    """A read-only connection to the global index and the stamp it was built for (None if it has none)."""
    con = sqlite3.connect(_uri(path(), "ro"), uri=True, check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("SELECT v FROM meta WHERE k='stamp'").fetchone()
    except sqlite3.Error:
        con.close()
        raise
    return con, (row[0] if row else None)


def open_current(corpora, wait=True):
    """(read-only connection to the global index or None, True if it is being brought up to date).
    With wait=False a request never waits for the first build; it gets None until one exists."""
    want = _stamp(corpora)
    con = None
    if os.path.exists(path()):
        try:
            con, have = _open()
        except sqlite3.Error:
            con, have = None, None
        if con is not None and have == want:
            return con, False
        if con is not None and have is None:        # not a finished index: never serve it
            con.close()
            con = None
    with _lock:
        failed = _state["failed"]
        running = _state["thread"] is not None and _state["thread"].is_alive()
        if not running and not (failed and failed[0] == want and time.time() - failed[1] < 300):
            _state["thread"] = threading.Thread(target=_build, args=(list(corpora), want), daemon=True,
                                                name="global-index")
            _state["thread"].start()
            running = True
        thread = _state["thread"]
    if con is None and running and wait:
        thread.join()                                # first build: nothing to serve yet
        try:
            con, have = _open()
        except sqlite3.Error:
            return None, False
        if have is None:
            con.close()
            return None, False
        return con, False
    return con, running


def _add_corpus(con, c):
    src = sqlite3.connect(_uri(c.db_path, "ro"), uri=True)
    try:
        lo, hi = year_range(c, src)
        docs = src.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    finally:
        src.close()
    con.execute("ATTACH DATABASE ? AS src", (_uri(c.db_path, "ro"),))
    try:
        con.execute("""INSERT INTO staging SELECT gkey(type, name), ?, id, key, name, type, description, aliases, auto,
                              doc_count, mention_count, first_year, last_year FROM src.entities""", (c.id,))
        # spelling variants that fold to one global entity: their documents, counted once
        for (gk,) in con.execute("SELECT gkey FROM staging WHERE cid=? GROUP BY gkey HAVING COUNT(*) > 1", (c.id,)).fetchall():
            ids = [r[0] for r in con.execute("SELECT id FROM staging WHERE cid=? AND gkey=?", (c.id, gk))]
            n = con.execute(f"SELECT COUNT(DISTINCT doc_id) FROM src.mentions WHERE entity_id IN ({','.join('?' * len(ids))})",
                            ids).fetchone()[0]
            con.execute("INSERT INTO distinct_docs VALUES(?,?,?)", (gk, c.id, n))
        con.execute("""INSERT INTO years SELECT ?, year, COUNT(*) FROM src.documents
                       WHERE year BETWEEN ? AND ? GROUP BY year""", (c.id, lo, hi))
        con.execute("INSERT INTO corpora VALUES(?,?,?,?,?)", (c.id, c.title, docs, lo, hi))
        con.commit()
    finally:
        con.commit()
        con.execute("DETACH DATABASE src")


def _build(corpora, stamp):
    t0 = time.time()
    tmp = f"{path()}.{os.getpid()}-{threading.get_ident()}.tmp"    # unique: app processes may share a data dir
    skipped = []
    try:
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        # journal_mode=OFF: no journal file, so SQLite's moved-file check (which misfires on a new exFAT file) never runs
        con = sqlite3.connect(_uri(tmp), uri=True)
        con.create_function("gkey", 2, gkey, deterministic=True)
        con.executescript("""
            PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
            CREATE TEMP TABLE staging(gkey TEXT, cid TEXT, id INTEGER, key TEXT, name TEXT, type TEXT, description TEXT,
                aliases TEXT, auto INTEGER, doc_count INTEGER, mention_count INTEGER, first_year INTEGER, last_year INTEGER);
            CREATE TEMP TABLE distinct_docs(gkey TEXT, cid TEXT, n INTEGER);
            CREATE TABLE corpora(cid TEXT PRIMARY KEY, title TEXT, docs INTEGER, lo INTEGER, hi INTEGER);
            CREATE TABLE years(cid TEXT, year INTEGER, n INTEGER);
            CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
        """)
        for c in corpora:
            try:
                _add_corpus(con, c)
            except Exception as e:          # one unreadable corpus must not take the others down
                skipped.append(c.id)
                print(f"[global] skipping {c.id}: {e}", flush=True)
                for table in ("staging", "distinct_docs", "years", "corpora"):
                    con.execute(f"DELETE FROM {table} WHERE cid=?", (c.id,))
                con.commit()
        con.executescript("""
            CREATE INDEX temp.distinct_docs_key ON distinct_docs(gkey, cid);
            CREATE TEMP TABLE per_corpus AS
                SELECT gkey, cid, SUM(doc_count) docs, SUM(mention_count) mc, MIN(first_year) fy, MAX(last_year) ly,
                       MIN(auto) au FROM staging GROUP BY gkey, cid;
            UPDATE per_corpus SET docs = (SELECT n FROM distinct_docs d WHERE d.gkey = per_corpus.gkey AND d.cid = per_corpus.cid)
                WHERE EXISTS (SELECT 1 FROM distinct_docs d WHERE d.gkey = per_corpus.gkey AND d.cid = per_corpus.cid);
            -- the representative row (name, description, aliases): curated before auto-detected, then the largest
            CREATE TABLE entities AS
            WITH sums AS (SELECT gkey, SUM(docs) dc, SUM(mc) mc, MIN(fy) fy, MAX(ly) ly, COUNT(*) nc, MIN(au) au
                          FROM per_corpus GROUP BY gkey),
                 ranked AS (SELECT gkey, name, type, description, aliases,
                                   ROW_NUMBER() OVER (PARTITION BY gkey ORDER BY auto, doc_count DESC) rn FROM staging)
            SELECT s.gkey, r.name, r.type, r.description, s.au AS auto, r.aliases, s.dc AS doc_count,
                   s.mc AS mention_count, s.fy AS first_year, s.ly AS last_year, s.nc AS n_corpora
            FROM sums s JOIN ranked r ON r.gkey = s.gkey AND r.rn = 1;
            CREATE UNIQUE INDEX entities_gkey ON entities(gkey);
            CREATE INDEX entities_dc ON entities(doc_count DESC);
            CREATE INDEX entities_type ON entities(type, doc_count DESC);
            CREATE TABLE local AS SELECT gkey, cid, key, name, doc_count, mention_count FROM staging;
            CREATE INDEX local_gkey ON local(gkey);
            CREATE TABLE type_counts AS SELECT type, COUNT(*) n FROM entities GROUP BY type;
        """)
        con.executemany("INSERT INTO meta VALUES(?,?)", [("stamp", stamp), ("built", time.strftime("%Y-%m-%d %H:%M:%S")),
                                                         ("skipped", ",".join(skipped))])
        con.commit()
        con.close()
        os.replace(tmp, path())
        print(f"[global] index of {len(corpora) - len(skipped)} corpora built in {time.time() - t0:.1f}s", flush=True)
    except Exception:
        traceback.print_exc()
        with _lock:
            _state["failed"] = (stamp, time.time())
        try:
            os.remove(tmp)
        except OSError:
            pass
