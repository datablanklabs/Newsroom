"""
Newsroom — a local search engine, entity index and relationship explorer for leaked, declassified
and published document collections. Each corpus (corpora/<id>.toml) has its own index
(data/<id>/index.db) and lives under /c/<id>/; the home page lists them all and searches across them,
and /all/ has entities, an entity network and timelines across every corpus (lib/globalindex.py).

Run:   .venv/bin/python app/app.py            (then open http://127.0.0.1:5001)
"""
import collections
import io
import json
import mailbox
import math
import mimetypes
import os
import re
import sqlite3
import sys

from flask import Blueprint, Flask, abort, g, has_request_context, jsonify, redirect, render_template, request, send_file, url_for
from markupsafe import Markup, escape

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, PROJECT)
from lib import archives, globalindex, packs  # noqa: E402
from lib.globalindex import gkey  # noqa: E402
from lib.config import CORPORA_DIR, list_corpora  # noqa: E402
from lib.text import TYPE_LABEL, TYPES  # noqa: E402

TYPE_SINGULAR = {"person": "Person", "agency": "Agency", "company": "Company", "program": "Program / codename",
                 "technology": "Technology", "place": "Place", "organization": "Organization", "idea": "Idea / theme",
                 "identifier": "Identifier / address"}
KIND_LABEL = {"pdf": "PDF", "image": "Image", "image-set": "Page scans", "html": "Web page", "text": "Text", "email": "Email",
              "msg": "Email (Outlook)", "docx": "Word", "doc": "Word (legacy)", "pptx": "PowerPoint", "xlsx": "Excel",
              "xls": "Excel (legacy)", "odf": "OpenDocument", "rtf": "RTF", "csv": "CSV table", "record": "Record",
              "cable": "Diplomatic cable", "chat": "Chat log", "war-log": "War log"}

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True          # must be set before jinja_env is first touched
bp = Blueprint("c", __name__, url_prefix="/c/<cid>")


# --------------------------------------------------------------------------- corpora

_corpora = {"stamp": None, "list": []}


def corpora():
    """All configured corpora, reloaded when a config file changes (checked once per request)."""
    if has_request_context() and "corpora" in g:
        return g.corpora
    try:
        stamp = tuple(sorted((f, os.path.getmtime(os.path.join(CORPORA_DIR, f))) for f in os.listdir(CORPORA_DIR)))
    except OSError:
        stamp = ()
    if stamp != _corpora["stamp"]:
        _corpora["stamp"], _corpora["list"] = stamp, list_corpora()
    if has_request_context():
        g.corpora = _corpora["list"]
    return _corpora["list"]


def get_corpus(cid):
    return next((c for c in corpora() if c.id == cid), None)


def built_corpora():
    return [c for c in corpora() if c.exists()]


def default_corpus():
    built = built_corpora()
    return next((c for c in built if c.id == os.environ.get("NEWSROOM_DEFAULT", "snowden")), built[0] if built else None)


def connect(corpus):
    con = sqlite3.connect(f"file:{corpus.db_path}?mode=ro", uri=True, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


# --------------------------------------------------------------------------- db helpers

def db():
    if "db" not in g:
        g.db = connect(g.corpus)
    return g.db


@app.teardown_appcontext
def close_db(_):
    cons = [g.pop("db", None), g.pop("gdb", None)] + list(g.pop("ccons", {}).values())
    for con in cons:
        if con is not None:
            con.close()


def q(sql, args=(), con=None):
    return (con or db()).execute(sql, args).fetchall()


def q1(sql, args=(), con=None):
    return (con or db()).execute(sql, args).fetchone()


def has_table(name, con=None):
    return q1("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,), con) is not None


def present_types():
    if "types" not in g:
        have = {r["type"] for r in q("SELECT DISTINCT type FROM entities")}
        g.types = [t for t in TYPES if t in have]
    return g.types


def year_bounds():
    """Year range for charts: the corpus config, else the data (ignoring stray outliers)."""
    return globalindex.year_range(g.corpus, db())


@bp.url_value_preprocessor
def pull_corpus(endpoint, values):
    g.cid = values.pop("cid")
    g.corpus = get_corpus(g.cid)
    if g.corpus is None or not g.corpus.exists():
        abort(404, description=f"Corpus {g.cid!r} is not configured or not built yet.")


@bp.url_defaults
def add_corpus(endpoint, values):
    if "cid" not in values and getattr(g, "cid", None):
        values["cid"] = g.cid


@app.context_processor
def inject():
    corpus = getattr(g, "corpus", None)
    ctx = dict(TYPE_LABEL=TYPE_LABEL, TYPE_SINGULAR=TYPE_SINGULAR, KIND_LABEL=KIND_LABEL, corpus=corpus,
               all_corpora=built_corpora(), TYPE_ORDER=TYPES)
    if corpus is not None and request.blueprint == "c":
        ctx["TYPE_ORDER"] = present_types()
        ctx["base"] = url_for("c.index").rstrip("/")
        ctx["has_findings"] = bool(corpus.findings and os.path.exists(corpus.findings))
    elif request.blueprint == "all":
        ctx["base"] = url_for("all.entities").rsplit("/", 1)[0]
        ctx["global_view"] = True
        if built_corpora():
            have = {r["type"] for r in q("SELECT type FROM type_counts", (), gdb())}
            ctx["TYPE_ORDER"] = [t for t in TYPES if t in have]
            ctx["global_updating"] = g.global_updating
    return ctx


@app.template_filter("num")
def fmt_num(n):
    return f"{n:,}" if isinstance(n, int) else n


# --------------------------------------------------------------------------- search helpers

FTS_SPECIAL = re.compile(r'["*():^+\-]|\b(?:AND|OR|NOT|NEAR)\b')


def to_fts_query(user_q):
    """Pass through FTS5 syntax if the user used it; otherwise AND the terms (quoted)."""
    user_q = user_q.strip()
    if not user_q:
        return ""
    if FTS_SPECIAL.search(user_q):
        return user_q
    terms = re.findall(r"[\w'’.&]+", user_q)
    return " ".join('"' + t.replace('"', "") + '"' for t in terms)


def highlight_terms(user_q):
    terms = [t for t in re.findall(r"[\w'’&]+", user_q) if t.upper() not in ("AND", "OR", "NOT", "NEAR") and len(t) > 1]
    return terms


FACETS = ("collection", "origin", "classification", "kind")


def run_search(user_q, filters, limit_pages=3000, con=None):
    browse = user_q.strip() in ("", "*")
    fts = "" if browse else to_fts_query(user_q)
    hits = collections.OrderedDict()
    err = None
    if fts:
        try:
            rows = q("""SELECT p.doc_id, p.page_no, bm25(pages_fts) AS score,
                               snippet(pages_fts, 0, '[[[', ']]]', ' … ', 28) AS snip
                        FROM pages_fts JOIN pages p ON p.rowid = pages_fts.rowid
                        WHERE pages_fts MATCH ? ORDER BY score LIMIT ?""", (fts, limit_pages), con)
        except sqlite3.OperationalError as e:
            rows, err = [], f"Search syntax error: {e}"
        for r in rows:
            h = hits.setdefault(r["doc_id"], {"score": 0.0, "pages": [], "snips": []})
            h["score"] += r["score"]          # bm25 is negative: more matching pages → more relevant
            h["pages"].append(r["page_no"])
            if len(h["snips"]) < 3:
                h["snips"].append((r["page_no"], r["snip"]))
        # title / filename matches
        try:
            for r in q("SELECT id, bm25(docs_fts) AS s FROM docs_fts WHERE docs_fts MATCH ? LIMIT 500", (fts,), con):
                h = hits.setdefault(r["id"], {"score": 0.0, "pages": [], "snips": []})
                h["score"] += r["s"] * 3
                h["title_hit"] = True
        except sqlite3.OperationalError:
            pass
    for key in ("entity", "entity2"):
        if not filters.get(key):
            continue
        ent_docs = {r["doc_id"]: r["n"] for r in q(
            "SELECT doc_id, SUM(count) n FROM mentions WHERE entity_id=? GROUP BY doc_id", (filters[key],), con)}
        if fts or (key == "entity2" and filters.get("entity")):
            hits = collections.OrderedDict((k, v) for k, v in hits.items() if k in ent_docs)
        else:
            for d, n in sorted(ent_docs.items(), key=lambda x: -x[1]):
                hits[d] = {"score": -n, "pages": [], "snips": []}
    if browse and not hits and not filters.get("entity"):
        # filter-only browsing ("*"): every document, narrowed by the facet filters below
        for r in q("SELECT id FROM documents ORDER BY doc_date", (), con):
            hits[r["id"]] = {"score": 0.0, "pages": [], "snips": []}
    if not hits:
        return [], {}, err
    ids = list(hits)
    docs = {}
    for i in range(0, len(ids), 900):
        chunk = ids[i:i + 900]
        for r in q(f"""SELECT id, relpath, kind, title, collection, publisher, doc_date, date_source, year, pages,
                              origin, classification, summary, author FROM documents
                       WHERE id IN ({','.join('?'*len(chunk))})""", chunk, con):
            docs[r["id"]] = dict(r)
    results = []
    for doc_id, h in hits.items():
        d = docs.get(doc_id)
        if not d:
            continue
        if any(filters.get(f) and d[f] != filters[f] for f in FACETS):
            continue
        if filters.get("year_from") and (not d["year"] or d["year"] < filters["year_from"]):
            continue
        if filters.get("year_to") and (not d["year"] or d["year"] > filters["year_to"]):
            continue
        d.update(score=h["score"], match_pages=sorted(set(h["pages"])), snips=h["snips"], title_hit=h.get("title_hit"))
        results.append(d)
    sort = filters.get("sort", "relevance")
    if sort == "date":
        results.sort(key=lambda d: (d["doc_date"] or "9999"))
    elif sort == "date_desc":
        results.sort(key=lambda d: (d["doc_date"] or "0000"), reverse=True)
    else:
        results.sort(key=lambda d: d["score"])
    facets = {k: collections.Counter(d[k] or "—" for d in results) for k in FACETS}
    facets["year"] = collections.Counter(d["year"] for d in results if d["year"])
    return results, facets, err


def render_snippet(s):
    s = str(escape(s)).replace("[[[", "<mark>").replace("]]]", "</mark>")
    return Markup(re.sub(r"\s+", " ", s))


app.jinja_env.filters["snippet"] = render_snippet


def highlight_text(text, terms):
    out = str(escape(text))
    if terms:
        pat = re.compile(r"(?i)\b(" + "|".join(re.escape(str(escape(t))) for t in terms) + r")")
        out = pat.sub(r"<mark>\1</mark>", out)
    return Markup(out)


# --------------------------------------------------------------------------- entity helpers (per corpus and global)
# The global index's entities table has the same columns as a corpus's (plus gkey and n_corpora).

def entity_rows(con, t, user_q, show_auto, limit=1000):
    """The entity list: optionally one type, a name filter and no auto-detected entities; most documented first."""
    sql, args = "SELECT * FROM entities WHERE 1=1", []
    if t:
        sql += " AND type=?"
        args.append(t)
    if user_q:
        sql += " AND (name LIKE ? OR aliases LIKE ?)"
        args += [f"%{user_q}%"] * 2
    if not show_auto:
        sql += " AND auto=0"
    return q(sql + " ORDER BY doc_count DESC LIMIT ?", (*args, limit), con)


def entity_matches(con, user_q, cols="id, name, type, doc_count", limit=20):
    """Autocomplete: the exact name first, then names starting with the text, then the most documented."""
    return q(f"""SELECT {cols} FROM entities WHERE name LIKE ? OR aliases LIKE ?
                 ORDER BY (LOWER(name) = LOWER(?)) DESC, (name LIKE ?) DESC, doc_count DESC LIMIT ?""",
             (f"%{user_q}%", f"%{user_q}%", user_q, f"{user_q}%", limit), con)


def series_values(pts, totals, mode):
    """Timeline values for every year with dated documents: documents, or their share (%) of the year's."""
    vals = []
    for y in sorted(totals):
        v = pts.get(y, 0)
        if mode == "share":
            v = round(100.0 * v / totals[y], 2) if totals[y] else 0
        vals.append({"year": y, "value": v})
    return vals


def chunked(xs, n=900):
    xs = list(xs)
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def ph(xs):
    return ",".join("?" * len(xs))


def top_documents(con, ids, also=None, limit=400):
    """Documents mentioning any of ids (and one of also, if given), most mentions first, with their pages.
    Ranked on mentions before documents are read: an entity can be in 100,000+ documents."""
    both, args = "", list(ids)
    if also:
        both = f" AND doc_id IN (SELECT doc_id FROM mentions WHERE entity_id IN ({ph(also)}))"
        args += also
    return q(f"""SELECT d.id, d.title, d.doc_date, d.year, d.collection, d.origin, d.classification, x.n, x.pg
                 FROM (SELECT doc_id, SUM(count) n, GROUP_CONCAT(page_no) pg FROM mentions
                       WHERE entity_id IN ({ph(ids)}){both} GROUP BY doc_id ORDER BY n DESC LIMIT ?) x
                 JOIN documents d ON d.id = x.doc_id ORDER BY x.n DESC""", (*args, limit), con)


def year_counts(con, pairs, lo, hi):
    """{key: {year: documents}} for (entity id, key) pairs; a document of several ids with one key counts once.
    (Starting from the entities lets SQLite use the mentions index; a plain year filter makes it scan.)"""
    out = collections.defaultdict(collections.Counter)
    if pairs:
        for r in q(f"""WITH ent(id, k) AS (VALUES {','.join(['(?,?)'] * len(pairs))})
                       SELECT ent.k, d.year, COUNT(DISTINCT d.id) n FROM ent JOIN mentions m ON m.entity_id = ent.id
                       JOIN documents d ON d.id = m.doc_id WHERE d.year BETWEEN ? AND ? GROUP BY ent.k, d.year""",
                   [x for p in pairs for x in p] + [lo, hi], con):
            out[r["k"]][r["year"]] += r["n"]
    return out


def group_neighbours(neighbours):
    """(up to 12 co-occurring entities per type, the 20 most distinctive with >= 3 shared documents)."""
    by_type = collections.OrderedDict((t, []) for t in TYPES)
    for n in neighbours:
        if len(by_type[n["type"]]) < 12:
            by_type[n["type"]].append(n)
    return by_type, sorted([n for n in neighbours if n["docs"] >= 3], key=lambda n: -n["npmi"])[:20]


# --------------------------------------------------------------------------- library (all corpora)

@app.route("/")
def library():
    cards = []
    for c in corpora():
        card = {"c": c, "built": c.exists()}
        if card["built"]:
            con = connect(c)
            try:
                meta = {r["k"]: r["v"] for r in q("SELECT k, v FROM meta", (), con)}
                card.update(docs=int(meta.get("documents", 0)), pages=int(meta.get("pages", 0)), built_at=meta.get("built", ""),
                            entities=q1("SELECT COUNT(*) c FROM entities", (), con)["c"],
                            years=q1("SELECT MIN(year) lo, MAX(year) hi FROM documents WHERE year BETWEEN ? AND ?",
                                     (c.dates["min_year"], c.dates["max_year"]), con))
            finally:
                con.close()
        cards.append(card)
    return render_template("library.html", cards=cards)


@app.route("/search-all")
def search_all():
    user_q = request.args.get("q", "").strip()
    sections = []
    if user_q and user_q != "*":
        like = f"%{user_q}%"
        for c in built_corpora():
            con = connect(c)
            try:
                results, _, err = run_search(user_q, {}, limit_pages=600, con=con)
                total, capped = len(results), False
                fts = to_fts_query(user_q)
                if fts and not err:
                    total = q1("""SELECT COUNT(*) c FROM (SELECT DISTINCT p.doc_id FROM pages_fts
                                  JOIN pages p ON p.rowid = pages_fts.rowid WHERE pages_fts MATCH ? LIMIT 10000)""", (fts,), con)["c"]
                    total, capped = max(total, len(results)), total >= 10000
                ents = q("""SELECT id, name, type, doc_count FROM entities WHERE name LIKE ? OR aliases LIKE ?
                            ORDER BY doc_count DESC LIMIT 6""", (like, like), con)
            finally:
                con.close()
            if results or ents:
                sections.append({"c": c, "total": total, "capped": capped, "results": results[:5], "err": err, "ents": ents})
        sections.sort(key=lambda s: -s["total"])
    gents = []
    if user_q and user_q != "*" and len(user_q) >= 2 and built_corpora() and gdb(required=False) is not None:
        gents = entity_matches(gdb(), user_q, "gkey, name, type, doc_count, n_corpora", limit=12)
    return render_template("search_all.html", q=user_q, sections=sections, gents=gents)


# legacy single-corpus URLs (bookmarks from the Snowden-only version) -> default corpus
for _rule, _ep in (("/search", "search"), ("/entities", "entities"), ("/graph", "graph"), ("/timeline", "timeline"),
                   ("/findings", "findings"), ("/doc/<doc_id>", "doc"), ("/entity/<int:eid>", "entity"),
                   ("/file/<doc_id>", "original"), ("/file/<doc_id>/<int:n>", "original")):
    def _legacy(_ep=_ep, **kw):
        c = default_corpus()
        if c is None:
            abort(404)
        return redirect(url_for(f"c.{_ep}", cid=c.id, **kw, **request.args.to_dict()), code=301)
    app.add_url_rule(_rule, f"legacy_{_ep}_{_rule.count('/')}", _legacy)


# --------------------------------------------------------------------------- corpus pages

@bp.route("/")
def index():
    stats = dict(
        docs=q1("SELECT COUNT(*) c FROM documents")["c"],
        pages=q1("SELECT COUNT(*) c FROM pages")["c"],
        ocr=q1("SELECT COUNT(*) c FROM pages WHERE ocr=1")["c"],
        entities=q1("SELECT COUNT(*) c FROM entities")["c"],
        edges=q1("SELECT COUNT(*) c FROM edges")["c"],
        relations=q1("SELECT COUNT(*) c FROM relations")["c"] if has_table("relations") else 0,
        built=(q1("SELECT v FROM meta WHERE k='built'") or {"v": ""})["v"],
    )
    lo, hi = year_bounds()
    by_year = [dict(r) for r in q("SELECT year, COUNT(*) n FROM documents WHERE year BETWEEN ? AND ? GROUP BY year ORDER BY year", (lo, hi))]
    by_collection = q("SELECT collection, COUNT(*) n, SUM(pages) p FROM documents GROUP BY collection ORDER BY n DESC LIMIT 40")
    by_origin = q("SELECT origin, COUNT(*) n FROM documents GROUP BY origin ORDER BY n DESC LIMIT 25")
    by_kind = q("SELECT kind, COUNT(*) n FROM documents GROUP BY kind ORDER BY n DESC")
    top = {t: q("SELECT id, name, type, doc_count FROM entities WHERE type=? ORDER BY doc_count DESC LIMIT 14", (t,))
           for t in present_types()}
    return render_template("index.html", stats=stats, by_year=by_year, by_collection=by_collection,
                           by_origin=by_origin, by_kind=by_kind, top=top)


@bp.route("/search")
def search():
    user_q = request.args.get("q", "").strip()
    filters = {f: request.args.get(f) or None for f in FACETS}
    filters.update({
        "year_from": request.args.get("year_from", type=int),
        "year_to": request.args.get("year_to", type=int),
        "entity": request.args.get("entity", type=int),
        "entity2": request.args.get("entity2", type=int),
        "sort": request.args.get("sort", "relevance"),
    })
    page = max(1, request.args.get("page", 1, type=int))
    per = 25
    results, facets, err = run_search(user_q, filters) if (user_q or filters["entity"]) else ([], {}, None)
    entity = q1("SELECT * FROM entities WHERE id=?", (filters["entity"],)) if filters["entity"] else None
    entity2 = q1("SELECT * FROM entities WHERE id=?", (filters["entity2"],)) if filters["entity2"] else None
    ent_matches = []
    if user_q and user_q != "*" and len(user_q) >= 2:
        like = f"%{user_q}%"
        ent_matches = q("""SELECT id, name, type, doc_count FROM entities
                           WHERE name LIKE ? OR aliases LIKE ? ORDER BY doc_count DESC LIMIT 12""", (like, like))
    total = len(results)
    results = results[(page - 1) * per: page * per]
    # entities present in each result (top few) for context chips
    for d in results:
        d["ents"] = q("""SELECT e.id, e.name, e.type, SUM(m.count) n FROM mentions m JOIN entities e ON e.id=m.entity_id
                         WHERE m.doc_id=? AND e.type IN ('person','program','company','agency','organization')
                         GROUP BY e.id ORDER BY n DESC LIMIT 8""", (d["id"],))
    args = request.args.to_dict()
    args.pop("page", None)
    return render_template("search.html", q=user_q, results=results, total=total, page=page, per=per,
                           facets=facets, filters=filters, entity=entity, entity2=entity2, ent_matches=ent_matches, err=err, args=args)


def has_original(d):
    src = json.loads(d["src"] or "{}") if "src" in d.keys() and d["src"] else {}
    return bool(src) and not ({"record", "node"} & set(src))


@bp.route("/doc/<doc_id>")
def doc(doc_id):
    d = q1("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not d:
        abort(404)
    d = dict(d)
    d["duplicates"] = json.loads(d["duplicates"] or "[]")
    d["sources"] = json.loads(d["sources"] or "[]")
    d["fields"] = json.loads(d.get("fields") or "{}") if d.get("fields") else {}
    d["src_obj"] = json.loads(d.get("src") or "{}") if d.get("src") else {}
    d["has_original"] = has_original(d)
    user_q = request.args.get("q", "")
    terms = highlight_terms(user_q)
    pages = [dict(r) for r in q("SELECT page_no, text, ocr FROM pages WHERE doc_id=? ORDER BY page_no", (doc_id,))]
    for p in pages:
        p["html"] = highlight_text(p["text"], terms)
    ents = q("""SELECT e.id, e.name, e.type, e.auto, SUM(m.count) n, COUNT(*) np, GROUP_CONCAT(m.page_no) pg
                FROM mentions m JOIN entities e ON e.id=m.entity_id WHERE m.doc_id=?
                GROUP BY e.id ORDER BY n DESC""", (doc_id,))
    grouped = collections.OrderedDict((t, []) for t in TYPES)
    for e in ents:
        grouped.setdefault(e["type"], []).append(e)
    relations = []
    if has_table("relation_docs"):
        relations = q("""SELECT r.type, a.id aid, a.name aname, a.type atype, b.id bid, b.name bname, b.type btype
                         FROM relation_docs r JOIN entities a ON a.id=r.src JOIN entities b ON b.id=r.dst
                         WHERE r.doc_id=? LIMIT 200""", (doc_id,))
    # documents sharing the most distinctive entities (weighted by inverse document frequency)
    n_docs = q1("SELECT COUNT(*) c FROM documents")["c"]
    related = q("""
        WITH mine AS (SELECT DISTINCT entity_id FROM mentions WHERE doc_id=?)
        SELECT d.id, d.title, d.doc_date, d.collection,
               SUM(1.0 / e.doc_count) AS w, COUNT(DISTINCT m.entity_id) shared
        FROM mentions m JOIN mine ON mine.entity_id=m.entity_id
        JOIN entities e ON e.id=m.entity_id JOIN documents d ON d.id=m.doc_id
        WHERE m.doc_id != ? AND e.type != 'idea' AND e.doc_count < ?
        GROUP BY m.doc_id ORDER BY w DESC LIMIT 12""", (doc_id, doc_id, max(400, n_docs // 8)))
    return render_template("doc.html", d=d, pages=pages, grouped=grouped, q=user_q, related=related, relations=relations)


@bp.route("/entity/<int:eid>")
def entity(eid):
    e = q1("SELECT * FROM entities WHERE id=?", (eid,))
    if not e:
        abort(404)
    e = dict(e)
    e["aliases"] = json.loads(e["aliases"] or "[]")
    docs = top_documents(db(), [eid])
    by_year = [{"year": y, "n": n} for y, n in sorted(year_counts(db(), [(eid, eid)], *year_bounds())[eid].items())]
    neighbors = q("""SELECT e.id, e.name, e.type, x.docs, x.npmi FROM
                       (SELECT dst AS o, docs, npmi FROM edges WHERE src=? UNION ALL
                        SELECT src AS o, docs, npmi FROM edges WHERE dst=?) x
                     JOIN entities e ON e.id = x.o ORDER BY x.docs DESC LIMIT 400""", (eid, eid))
    by_type, distinctive = group_neighbours(neighbors)
    relations = []
    if has_table("relations"):
        relations = q("""SELECT 'out' dir, r.type, r.docs, r.first_date, r.last_date, e.id, e.name, e.type etype
                         FROM relations r JOIN entities e ON e.id=r.dst WHERE r.src=?
                         UNION ALL
                         SELECT 'in' dir, r.type, r.docs, r.first_date, r.last_date, e.id, e.name, e.type etype
                         FROM relations r JOIN entities e ON e.id=r.src WHERE r.dst=?
                         ORDER BY docs DESC LIMIT 300""", (eid, eid))
    # the same entity in other corpora, matched like the global views do (type and folded name)
    gk, elsewhere = gkey(e["type"], e["name"]), []
    if gdb(required=False) is not None:
        elsewhere = [p for p in g_per_corpus(gk, resolve([gk])) if p["c"].id != g.corpus.id]
    else:                         # no global index yet: the same name, ignoring case
        for c in built_corpora():
            con = ccon(c.id) if c.id != g.corpus.id else None
            r = q1("SELECT id, doc_count FROM entities WHERE type=? AND name=? COLLATE NOCASE ORDER BY doc_count DESC",
                   (e["type"], e["name"]), con) if con is not None else None
            if r:
                elsewhere.append({"c": c, "id": r["id"], "docs": r["doc_count"]})
    return render_template("entity.html", e=e, docs=docs, by_year=by_year, by_type=by_type, distinctive=distinctive,
                           relations=relations, elsewhere=elsewhere, gk=gk)


@bp.route("/entities")
def entities():
    t = request.args.get("type", "")
    user_q = request.args.get("q", "")
    show_auto = request.args.get("hide_auto") != "1"
    rows = entity_rows(db(), t, user_q, show_auto)
    counts = {r["type"]: r["n"] for r in q("SELECT type, COUNT(*) n FROM entities GROUP BY type")}
    return render_template("entities.html", rows=rows, t=t, q=user_q, counts=counts, show_auto=show_auto)


@bp.route("/graph")
def graph():
    n_rel = q1("SELECT COUNT(*) c FROM relations")["c"] if has_table("relations") else 0
    return render_template("graph.html", focus=request.args.get("focus", type=int), n_relations=n_rel,
                           hide_hubs=g.corpus.ui.get("hide_hubs", 800), hub_hint=g.corpus.ui.get("hub_hint", ""),
                           scope_title=g.corpus.title, window=g.corpus.index["window"])


def timeline_presets(corpus):
    presets = [tuple(p) for p in corpus.ui.get("timeline_presets", [])]
    for p in packs.timeline_presets(corpus.packs):
        if p not in presets:
            presets.append(p)
    return presets


@bp.route("/timeline")
def timeline():
    return render_template("timeline.html", presets=timeline_presets(g.corpus), scope_title=g.corpus.title,
                           year_note=g.corpus.ui.get("year_note", ""))


@bp.route("/findings")
def findings():
    path = g.corpus.findings
    if not path or not os.path.exists(path):
        abort(404)
    import markdown
    with open(path, encoding="utf-8") as f:
        html = markdown.markdown(f.read(), extensions=["tables", "toc", "fenced_code"])
    return render_template("findings.html", body=Markup(html))


# --------------------------------------------------------------------------- APIs

REL_EDGES = "(SELECT MIN(src, dst) AS src, MAX(src, dst) AS dst, SUM(docs) AS docs, 0.0 AS npmi FROM relations GROUP BY 1, 2)"


@bp.route("/api/graph")
def api_graph():
    types = [t for t in request.args.get("types", ",".join(TYPES)).split(",") if t in TYPES]
    limit = min(request.args.get("limit", 150, type=int), 600)
    min_docs = request.args.get("min_docs", 3, type=int)
    metric = request.args.get("metric", "docs")
    focus = request.args.get("focus", type=int)
    hide_auto = request.args.get("hide_auto", "0") == "1"
    max_df = request.args.get("max_df", 10**9, type=int)
    use_rel = request.args.get("source") == "relations" and has_table("relations")
    edges = REL_EDGES if use_rel else "edges"
    if use_rel:
        metric, min_docs = "docs", min(min_docs, 1)
    ph = ",".join("?" * len(types)) or "''"
    auto_clause = " AND auto=0" if hide_auto else ""
    if focus:
        # ego network: focus + its strongest neighbours, then edges among them
        order = "x.npmi DESC" if metric == "npmi" else "x.docs DESC"
        nb = q(f"""SELECT x.o AS id FROM (SELECT dst AS o, docs, npmi FROM {edges} WHERE src=? UNION ALL
                                           SELECT src AS o, docs, npmi FROM {edges} WHERE dst=?) x
                   JOIN entities e ON e.id=x.o WHERE e.type IN ({ph}) AND x.docs >= ? AND e.doc_count <= ? {auto_clause.replace('auto', 'e.auto')}
                   ORDER BY {order} LIMIT ?""", (focus, focus, *types, min_docs, max_df, limit - 1))
        ids = [focus] + [r["id"] for r in nb]
    else:
        connected = " AND id IN (SELECT src FROM relations UNION SELECT dst FROM relations)" if use_rel else ""
        ids = [r["id"] for r in q(f"""SELECT id FROM entities WHERE type IN ({ph}) AND doc_count >= ? AND doc_count <= ? {auto_clause}{connected}
                                    ORDER BY doc_count DESC LIMIT ?""", (*types, 1 if use_rel else min_docs, max_df, limit))]
    if not ids:
        return jsonify(nodes=[], links=[])
    idph = ",".join("?" * len(ids))
    nodes = [dict(r) for r in q(f"SELECT id, name, type, doc_count, description, auto FROM entities WHERE id IN ({idph})", ids)]
    links = [dict(r) for r in q(f"""SELECT src AS source, dst AS target, docs, npmi FROM {edges}
                                     WHERE src IN ({idph}) AND dst IN ({idph}) AND docs >= ?""", (*ids, *ids, min_docs))]
    links = strongest_links(links, metric, request.args.get("k", 8, type=int))
    return jsonify(nodes=nodes, links=links, focus=focus)


def strongest_links(links, metric, k):
    """Keep a graph legible: per node, only its strongest k links."""
    key = (lambda l: l["npmi"]) if metric == "npmi" else (lambda l: l["docs"])
    keep = set()
    adj = collections.defaultdict(list)
    for i, l in enumerate(links):
        adj[l["source"]].append((key(l), i))
        adj[l["target"]].append((key(l), i))
    for n, lst in adj.items():
        for _, i in sorted(lst, reverse=True)[:k]:
            keep.add(i)
    return [links[i] for i in sorted(keep)]


@bp.route("/api/entities")
def api_entities():
    return jsonify([dict(r) for r in entity_matches(db(), request.args.get("q", ""))])


@bp.route("/api/timeline")
def api_timeline():
    ids = [int(x) for x in (request.args.getlist("id") or request.args.get("ids", "").split(",")) if x.strip().isdigit()][:8]
    mode = request.args.get("mode", "docs")   # docs | share
    lo, hi = year_bounds()
    totals = {r["year"]: r["n"] for r in q("SELECT year, COUNT(*) n FROM documents WHERE year BETWEEN ? AND ? GROUP BY year", (lo, hi))}
    ents = {r["id"]: r for r in q(f"SELECT id, name, type FROM entities WHERE id IN ({ph(ids)})", ids)}
    counts = year_counts(db(), [(i, i) for i in ids if i in ents], lo, hi)
    series = [{"id": i, "name": ents[i]["name"], "type": ents[i]["type"], "values": series_values(counts[i], totals, mode)}
              for i in ids if i in ents]
    return jsonify(series=series, totals=[{"year": y, "n": n} for y, n in sorted(totals.items())], mode=mode)


# --------------------------------------------------------------------------- global views (every corpus)
# Entities are matched across corpora by type and folded name (lib/globalindex.py); their id in URLs and APIs
# is that global key ('person:lee harvey oswald'). Links, mentions and documents come from the corpus indexes.
# Spelling variants of one entity within a corpus count each document once; their co-occurrence links count
# the strongest variant's (recounting a merged pair exactly would mean rescanning the pages).

gb = Blueprint("all", __name__, url_prefix="/all")


def gdb(required=True):
    """The cross-corpus entity index, brought up to date in the background when a corpus is (re)built.
    Pages that only add global extras pass required=False: they never wait for the first build, and get
    None while there is no global index."""
    if "gdb" not in g:
        g.gdb, g.global_updating = globalindex.open_current(built_corpora(), wait=required)
    if g.gdb is None and required:
        abort(503, description="The cross-corpus index is not available yet; see the app log.")
    return g.gdb


def ccon(cid):
    """This request's connection to one corpus index (None if the corpus is no longer built)."""
    cons = g.setdefault("ccons", {})
    if cid not in cons:
        c = get_corpus(cid)
        cons[cid] = connect(c) if c is not None and c.exists() else None
    return cons[cid]


def ginfo(gkeys):
    """gkey -> merged entity row."""
    out = {}
    for part in chunked(gkeys):
        for r in q(f"SELECT * FROM entities WHERE gkey IN ({ph(part)})", part, gdb()):
            out[r["gkey"]] = r
    return out


def resolve(gkeys):
    """{corpus id: {gkey: [entity ids]}}: the corpus entities behind each global entity (several when spelling
    variants fold together), looked up by key in each corpus's current index, so a corpus rebuilt since the
    global index was made still resolves to the right entities."""
    by_cid = collections.defaultdict(dict)
    for part in chunked(gkeys):
        for r in q(f"SELECT cid, key, gkey FROM local WHERE gkey IN ({ph(part)})", part, gdb()):
            by_cid[r["cid"]][r["key"]] = r["gkey"]
    out = {}
    for cid, by_key in by_cid.items():
        con = ccon(cid)
        if con is None:
            continue
        ids = collections.defaultdict(list)
        for part in chunked(by_key):
            for r in q(f"SELECT id, key FROM entities WHERE key IN ({ph(part)})", part, con):
                ids[by_key[r["key"]]].append(r["id"])
        if ids:
            out[cid] = dict(ids)
    return out


def doc_count_in(con, ids, also=None):
    """Documents mentioning any of ids (and, with also, one of those as well), each counted once."""
    sql, args = f"SELECT COUNT(DISTINCT doc_id) n FROM mentions WHERE entity_id IN ({ph(ids)})", list(ids)
    if also:
        sql += f" AND doc_id IN (SELECT doc_id FROM mentions WHERE entity_id IN ({ph(also)}))"
        args += also
    return q1(sql, args, con)["n"]


def g_per_corpus(gk, res):
    """[{c, id, docs, mentions}] for each corpus with the global entity, most documents first; id is its
    best-documented entity there."""
    out = []
    for cid, by_g in res.items():
        ids = by_g.get(gk)
        if not ids:
            continue
        con = ccon(cid)
        rows = q(f"SELECT id, doc_count, mention_count FROM entities WHERE id IN ({ph(ids)}) ORDER BY doc_count DESC", ids, con)
        out.append({"c": get_corpus(cid), "id": rows[0]["id"],
                    "docs": rows[0]["doc_count"] if len(rows) == 1 else doc_count_in(con, ids),
                    "mentions": sum(r["mention_count"] for r in rows)})
    return sorted(out, key=lambda p: -p["docs"])


def total_docs():
    return q1("SELECT SUM(docs) n FROM corpora", (), gdb())["n"] or 1


def npmi(n_ab, df_a, df_b, n):
    p_ab, p_a, p_b = n_ab / n, df_a / n, df_b / n
    return 1.0 if p_ab >= 1 else round(math.log(p_ab / (p_a * p_b)) / -math.log(p_ab), 4)


def g_neighbours(gk, res, types=TYPES, per_corpus=400, rel=False):
    """Entities linked to a global entity: gkey -> shared documents (relation documents with rel=True), summed
    over corpora. Each corpus contributes its strongest per_corpus links."""
    nb = collections.Counter()
    for cid, by_g in res.items():
        ids, con = by_g.get(gk), ccon(cid)
        if not ids or (rel and not has_table("relations", con)):
            continue
        edges = REL_EDGES if rel else "edges"
        here = {}
        for r in q(f"""SELECT e.type, e.name, x.docs FROM (SELECT dst AS o, docs FROM {edges} WHERE src IN ({ph(ids)}) UNION ALL
                                                         SELECT src AS o, docs FROM {edges} WHERE dst IN ({ph(ids)})) x
                       JOIN entities e ON e.id = x.o WHERE e.type IN ({ph(types) or "''"}) ORDER BY x.docs DESC LIMIT ?""",
                   (*ids, *ids, *types, per_corpus), con):
            k = gkey(r["type"], r["name"])
            if k != gk and r["docs"] > here.get(k, 0):
                here[k] = r["docs"]
        nb.update(here)
    return nb


def g_year_counts(gkeys, res):
    """gkey -> {year: documents}, each corpus counted within its own chart years, each document once."""
    bounds = {r["cid"]: (r["lo"], r["hi"]) for r in q("SELECT cid, lo, hi FROM corpora", (), gdb())}
    want = set(gkeys)
    out = collections.defaultdict(collections.Counter)
    for cid, by_g in res.items():
        if cid in bounds:
            pairs = [(i, k) for k, ids in by_g.items() if k in want for i in ids]
            for k, years in year_counts(ccon(cid), pairs, *bounds[cid]).items():
                out[k].update(years)
    return out


def g_year_totals():
    return {r["year"]: r["n"] for r in q("SELECT year, SUM(n) n FROM years GROUP BY year", (), gdb())}


@gb.before_request
def need_corpora():
    if not built_corpora():
        abort(404, description="No corpus has been built yet.")


@gb.route("/")
def g_index():
    return redirect(url_for("all.entities"))


@gb.route("/entities", endpoint="entities")
def g_entities():
    t = request.args.get("type", "")
    user_q = request.args.get("q", "")
    show_auto = request.args.get("hide_auto") != "1"
    counts = {r["type"]: r["n"] for r in q("SELECT type, n FROM type_counts", (), gdb())}
    n_corpora = q1("SELECT COUNT(*) n FROM corpora", (), gdb())["n"]
    return render_template("all_entities.html", rows=entity_rows(gdb(), t, user_q, show_auto), t=t, q=user_q,
                           counts=counts, show_auto=show_auto, n_corpora=n_corpora)


@gb.route("/entity", endpoint="entity")
def g_entity():
    gk = request.args.get("key", "")
    with_k = request.args.get("with") or None
    found = ginfo([gk] + ([with_k] if with_k else []))
    if gk not in found:
        if g.global_updating:     # most likely from a corpus built since the global index was made
            return render_template("message.html", title="Updating",
                                   message="This entity is not in the cross-collection index yet: newly built collections "
                                           "are being added to it. Try again in a minute."), 503
        abort(404)
    e = dict(found[gk])
    e["aliases"] = json.loads(e["aliases"] or "[]")
    other = found.get(with_k)
    res = resolve([gk] + ([with_k] if other else []))
    per_corpus = g_per_corpus(gk, res)
    docs, n_docs, rels = [], 0, {}
    for cid, by_g in res.items():
        mine, theirs = by_g.get(gk), by_g.get(with_k) if other else None
        if not mine or (other and not theirs):
            continue
        c, con = get_corpus(cid), ccon(cid)
        if other:
            n_docs += doc_count_in(con, mine, theirs)
        docs += [dict(r, cid=cid, ctitle=c.title) for r in top_documents(con, mine, theirs)]
        if other or not has_table("relations", con):
            continue
        here = {}                 # within a corpus, relations of spelling variants count once
        for r in q(f"""SELECT 'out' dir, r.type, r.docs, r.first_date, r.last_date, e.name, e.type etype
                       FROM relations r JOIN entities e ON e.id=r.dst WHERE r.src IN ({ph(mine)})
                       UNION ALL
                       SELECT 'in' dir, r.type, r.docs, r.first_date, r.last_date, e.name, e.type etype
                       FROM relations r JOIN entities e ON e.id=r.src WHERE r.dst IN ({ph(mine)})""", mine + mine, con):
            k = (r["dir"], r["type"], gkey(r["etype"], r["name"]))
            if k not in here or r["docs"] > here[k]["docs"]:
                here[k] = dict(r)
        for (d, t, ok), r in here.items():
            x = rels.setdefault((d, t, ok), {"dir": d, "type": t, "gkey": ok, "name": r["name"], "etype": r["etype"],
                                             "docs": 0, "first_date": None, "last_date": None})
            x["docs"] += r["docs"]
            x["first_date"] = min(filter(None, (x["first_date"], r["first_date"])), default=None)
            x["last_date"] = max(filter(None, (x["last_date"], r["last_date"])), default=None)
    if not other:
        n_docs = sum(p["docs"] for p in per_corpus)
    docs.sort(key=lambda d: -d["n"])
    by_year = [{"year": y, "n": n} for y, n in sorted(g_year_counts([gk], res)[gk].items())]
    n_all = total_docs()
    nb = g_neighbours(gk, res)
    ninfo = ginfo(nb)
    neighbours = sorted(({"gkey": k, "name": ninfo[k]["name"], "type": ninfo[k]["type"], "docs": d,
                          "npmi": npmi(d, e["doc_count"], ninfo[k]["doc_count"], n_all)}
                         for k, d in nb.items() if k in ninfo), key=lambda n: -n["docs"])[:400]
    by_type, distinctive = group_neighbours(neighbours)
    relations = sorted(rels.values(), key=lambda r: -r["docs"])[:300]
    return render_template("all_entity.html", e=e, other=dict(other) if other else None, per_corpus=per_corpus,
                           docs=docs[:400], n_docs=n_docs, by_year=by_year, by_type=by_type, distinctive=distinctive,
                           relations=relations)


@gb.route("/graph", endpoint="graph")
def g_graph():
    n_rel = 0
    for c in built_corpora():
        con = ccon(c.id)
        if con is not None and has_table("relations", con):
            n_rel += q1("SELECT COUNT(*) c FROM relations", (), con)["c"]
    return render_template("graph.html", focus=request.args.get("focus"), n_relations=n_rel, hide_hubs=20000,
                           hub_hint="", scope_title="All collections", window=None)


_presets = {}      # "v": (corpus configs + built corpora, presets)


@gb.route("/timeline", endpoint="timeline")
def g_timeline():
    built = built_corpora()
    key = (_corpora["stamp"], tuple(c.id for c in built))     # config files' mtimes: preset edits show at once
    cached = _presets.get("v")
    if cached is None or cached[0] != key:
        presets = []
        for c in built:
            presets += [p for p in timeline_presets(c) if p not in presets]
        cached = _presets["v"] = (key, presets)
    return render_template("timeline.html", presets=cached[1], scope_title="All collections", year_note="")


@gb.route("/api/entities", endpoint="api_entities")
def g_api_entities():
    rows = entity_matches(gdb(), request.args.get("q", ""), "gkey AS id, name, type, doc_count, n_corpora")
    return jsonify([dict(r) for r in rows])


@gb.route("/api/timeline", endpoint="api_timeline")
def g_api_timeline():
    keys = [k for k in request.args.getlist("id") if k][:8]
    mode = request.args.get("mode", "docs")   # docs | share
    totals = g_year_totals()
    counts = g_year_counts(keys, resolve(keys))
    info = ginfo(keys)
    series = [{"id": k, "name": info[k]["name"], "type": info[k]["type"], "values": series_values(counts[k], totals, mode)}
              for k in keys if k in info]
    return jsonify(series=series, totals=[{"year": y, "n": n} for y, n in sorted(totals.items())], mode=mode)


@gb.route("/api/graph", endpoint="api_graph")
def g_api_graph():
    types = [t for t in request.args.get("types", ",".join(TYPES)).split(",") if t in TYPES]
    limit = min(request.args.get("limit", 150, type=int), 600)
    min_docs = request.args.get("min_docs", 3, type=int)
    metric = request.args.get("metric", "docs")
    focus = request.args.get("focus") or None
    hide_auto = request.args.get("hide_auto", "0") == "1"
    max_df = request.args.get("max_df", 10**9, type=int)
    rel = request.args.get("source") == "relations"
    if rel:
        metric, min_docs = "docs", min(min_docs, 1)
    n_all = total_docs()

    def allowed(r):
        return r["type"] in types and r["doc_count"] <= max_df and not (hide_auto and r["auto"])

    if focus:
        f = ginfo([focus]).get(focus)
        if f is None:
            return jsonify(nodes=[], links=[])
        nb = g_neighbours(focus, resolve([focus]), types, per_corpus=3 * limit, rel=rel)
        info = ginfo(nb)
        info[focus] = f
        cands = [(k, d) for k, d in nb.items() if d >= min_docs and k in info and allowed(info[k])]
        if metric == "npmi":
            cands.sort(key=lambda c: -npmi(c[1], f["doc_count"], info[c[0]]["doc_count"], n_all))
        else:
            cands.sort(key=lambda c: -c[1])
        keys = [focus] + [k for k, _ in cands[:limit - 1]]
    elif rel:
        linked = set()
        for c in built_corpora():
            con = ccon(c.id)
            if con is not None and has_table("relations", con):
                linked |= {gkey(r["type"], r["name"]) for r in q(
                    "SELECT type, name FROM entities WHERE id IN (SELECT src FROM relations UNION SELECT dst FROM relations)", (), con)}
        info = ginfo(linked)
        keys = sorted((k for k, r in info.items() if allowed(r)), key=lambda k: -info[k]["doc_count"])[:limit]
    else:
        info = {r["gkey"]: r for r in q(f"""SELECT * FROM entities WHERE type IN ({ph(types) or "''"}) AND doc_count BETWEEN ? AND ?
                                            {'AND auto=0' if hide_auto else ''} ORDER BY doc_count DESC LIMIT ?""",
                                        (*types, min_docs, max_df, limit), gdb())}
        keys = list(info)
    if not keys:
        return jsonify(nodes=[], links=[])
    nodes = [{"id": k, "name": info[k]["name"], "type": info[k]["type"], "doc_count": info[k]["doc_count"],
              "description": info[k]["description"], "auto": info[k]["auto"], "n_corpora": info[k]["n_corpora"]} for k in keys]
    pairs = collections.Counter()
    for cid, by_g in resolve(keys).items():
        con = ccon(cid)
        if rel and not has_table("relations", con):
            continue
        key_of = {i: k for k, ids in by_g.items() for i in ids}
        here = {}                 # within a corpus, links between spelling variants count once (the strongest)
        for r in q(f"SELECT src, dst, docs FROM {REL_EDGES if rel else 'edges'} WHERE src IN ({ph(key_of)}) AND dst IN ({ph(key_of)})",
                   (*key_of, *key_of), con):
            a, b = key_of[r["src"]], key_of[r["dst"]]
            if a != b:
                pk = (min(a, b), max(a, b))
                here[pk] = max(here.get(pk, 0), r["docs"])
        pairs.update(here)
    links = [{"source": a, "target": b, "docs": d, "npmi": 0.0 if rel else npmi(d, info[a]["doc_count"], info[b]["doc_count"], n_all)}
             for (a, b), d in pairs.items() if d >= min_docs]
    links = strongest_links(links, metric, request.args.get("k", 8, type=int))
    return jsonify(nodes=nodes, links=links, focus=focus)


# --------------------------------------------------------------------------- original files

def _safe_archive_path(rel):
    root = os.path.realpath(g.corpus.root or "")
    full = os.path.realpath(os.path.join(root, rel))
    if not root or not full.startswith(root + os.sep) or not os.path.isfile(full):
        abort(404)
    return full


SAFE_INLINE = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
               ".gif": "image/gif", ".tif": "image/tiff", ".tiff": "image/tiff", ".bmp": "image/bmp"}
AS_TEXT = {".html", ".htm", ".xhtml", ".txt", ".log", ".md", ".eml", ".emlx", ".csv", ".tsv"}


def _serve_bytes(data, name):
    """Only documents, never active content: PDFs and images inline, web pages/emails/text as plain text,
    office files as downloads."""
    ext = os.path.splitext(name)[1].lower()
    if ext in SAFE_INLINE:
        return send_file(io.BytesIO(data), mimetype=SAFE_INLINE[ext], download_name=os.path.basename(name))
    if ext in AS_TEXT:
        return send_file(io.BytesIO(data), mimetype="text/plain; charset=utf-8")
    return send_file(io.BytesIO(data), mimetype="application/octet-stream", as_attachment=True,
                     download_name=os.path.basename(name))


@bp.route("/file/<doc_id>")
@bp.route("/file/<doc_id>/<int:n>")
def original(doc_id, n=1):
    d = q1("SELECT kind, sources, member, filename, src FROM documents WHERE id=?", (doc_id,))
    if not d:
        abort(404)
    src = json.loads(d["src"] or "{}") if d["src"] else {}
    sources = json.loads(d["sources"] or "[]")
    if not src:   # index built before source descriptors existed
        src = {"zip": sources[0], "member": d["member"]} if d["member"] else ({"files": sources} if d["kind"] == "image-set" else {"file": sources[0]} if sources else {})
    max_bytes = g.corpus.extract["max_member_mb"] * 1_000_000
    if "zip" in src:
        # only ever the indexed member; other archive members (e.g. malware samples) are never touched
        data = archives.read_zip_member(_safe_archive_path(src["zip"]), src["member"], max_bytes)
        return _serve_bytes(data, src["member"])
    if "archive" in src:
        data = archives.read_member(_safe_archive_path(src["archive"]), src["atype"], src["member"], max_bytes)
        return _serve_bytes(data, src["member"])
    if "mbox" in src:
        box = mailbox.mbox(_safe_archive_path(src["mbox"]), create=False)
        try:
            data = box.get_bytes(list(box.iterkeys())[src["index"] - 1])
        finally:
            box.close()
        return _serve_bytes(data, "message.eml")
    if "files" in src:
        idx = n - 1
        if not 0 <= idx < len(src["files"]):
            abort(404)
        full = _safe_archive_path(src["files"][idx])
    elif "file" in src:
        full = _safe_archive_path(src["file"])
    else:
        abort(404)
    ext = os.path.splitext(full)[1].lower()
    if ext in SAFE_INLINE:
        return send_file(full, mimetype=SAFE_INLINE[ext])
    if ext in AS_TEXT or d["kind"] == "html":
        return send_file(full, mimetype="text/plain; charset=utf-8")   # never execute saved web pages
    return send_file(full, mimetype=mimetypes.guess_type(full)[0] or "application/octet-stream", as_attachment=True)


app.register_blueprint(bp)
app.register_blueprint(gb)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    built = [c.id for c in built_corpora()]
    print(f"Newsroom → http://127.0.0.1:{port}   corpora: {', '.join(built) or '(none built yet)'}")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
