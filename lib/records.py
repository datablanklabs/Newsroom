"""
Record adapters: structured datasets where one row/node becomes one document.

  type = "csv"   one document per row of a CSV/TSV file (Cablegate cables.csv, war logs, registries)
  type = "sql"   one document per row of the INSERT statements in a SQL dump (.sql, also inside
                 .7z/.zip/.tar): the Afghan War Diary, leaked application databases
  type = "chat"  chat logs in JSON: Jabber/XMPP message streams (the Conti leak), Telegram and Discord
                 exports, Slack folders, generic JSON/JSONL; one document per conversation per day
  type = "icij"  the ICIJ Offshore Leaks database export (Panama / Paradise / Pandora Papers,
                 Offshore Leaks, Bahamas Leaks): nodes-*.csv + relationships.csv. Every node becomes
                 an entity and a short record document; every relationship becomes a typed relation.

Each adapter is a generator of document dicts in the same shape build/extract.py writes.
"""
import csv
import datetime
import glob
import hashlib
import html
import json
import os
import re
import sys

from lib.dates import parse_date
from lib.formats import paginate
from lib.text import looks_like_company, normalize_person, norm_ws

csv.field_size_limit(sys.maxsize)


def doc_id_for(relpath):
    return hashlib.sha1(relpath.encode("utf-8")).hexdigest()[:12]


def record_files(root, rec):
    """Files (or, for icij, the folder) a [[records]] entry points at, relative to root."""
    pats = rec["path"] if isinstance(rec["path"], list) else [rec["path"]]
    out = []
    for p in pats:
        full = os.path.join(root, p)
        if rec.get("type") == "icij":
            if os.path.isdir(full):
                out.append(os.path.relpath(full, root))
            continue
        for f in sorted(glob.glob(full, recursive=True)):
            if os.path.isfile(f) or (os.path.isdir(f) and rec.get("type") in ("chat", "sql")):
                out.append(os.path.relpath(f, root))
    return out


# =========================================================================== shared: one row -> one document

def _cell(row, col):
    if not col:
        return ""
    if "{" in col:
        try:
            return col.format(**row)
        except (KeyError, IndexError, ValueError):
            return ""
    return row.get(col, "") or ""


def row_doc(rel, i, row, header, rec, corpus):
    """A record (dict of column -> value) -> document, using the column options of a [[records]] block."""
    d = corpus.dates
    row = {k: ("" if v is None else str(v)) for k, v in row.items()}
    rid = norm_ws(_cell(row, rec.get("id", ""))) or str(i)
    relpath = f"{rel}#{rid}"
    text_cols = rec.get("text") or header
    text = "\n".join(f"{c.upper()}: {row.get(c, '')}" if rec.get("label_text") else row.get(c, "")
                     for c in text_cols if row.get(c))
    meta = {"title": norm_ws(_cell(row, rec.get("title", "")) or rid)[:200]}
    if rec.get("date"):
        meta["date"] = parse_date(_cell(row, rec["date"]), rec.get("date_format"), d["min_year"], d["max_year"],
                                  d["two_digit_century"])
        meta["date_source"] = "record"
    for k in ("author", "origin", "classification"):
        if rec.get(k):
            meta[k] = norm_ws(_cell(row, rec[k]))[:200]
    ents = []
    for col, spec in rec.get("entities", {}).items():
        etype, prefix = (spec, "") if isinstance(spec, str) else (spec["type"], spec.get("prefix", ""))
        for v in str(row.get(col, "")).split(rec.get("entity_separator", "|")):
            v = norm_ws(v)
            if v and v.upper() not in ("NONE", "NULL", "N/A", "UNKNOWN", "NONE SELECTED"):
                ents.append({"type": etype, "name": prefix + v, "source": "metadata",
                             "description": f"{col} value in {os.path.basename(rel.split('!/')[0])}."})
    return {
        "id": doc_id_for(relpath), "relpath": relpath, "kind": rec.get("kind", "record"),
        "src": {"record": rel, "row": i}, "sources": [rel.split("!/")[0]], "sha1": doc_id_for(relpath + "\0" + text),
        "collection": rec.get("name"),
        "pages": [{"n": n, "text": t, "ocr": False} for n, t in enumerate(paginate(text, corpus.extract["text_page_chars"]), 1)],
        "meta": meta, "fields": {c: row.get(c, "") for c in rec.get("fields", []) if row.get(c)}, "entities": ents,
    }


def _sources(root, rel, exts, max_bytes=2_000_000_000):
    """(name, bytes) for a plain file, every matching file in a folder, or every matching member of
    an archive (.zip/.7z/.rar/.tar*), read in memory without unpacking anything to disk."""
    from lib import archives
    full = os.path.join(root, rel)
    wanted = lambda n: n.lower().endswith(tuple(exts)) and not os.path.basename(n).startswith("._")
    if os.path.isdir(full):
        for dp, dn, fns in os.walk(full):
            dn.sort()
            for fn in sorted(fns):
                if wanted(fn):
                    with open(os.path.join(dp, fn), "rb") as f:
                        yield os.path.relpath(os.path.join(dp, fn), root), f.read()
        return
    atype = archives.archive_type(full)
    if atype == "zip":
        for name, size, enc in archives.zip_members(full):
            if wanted(name) and not enc and size <= max_bytes:
                yield f"{rel}!/{name}", archives.read_zip_member(full, name)
    elif atype:
        for name, data, _ in archives.stream_members(full, atype, wanted, max_bytes):
            if data is not None:
                yield f"{rel}!/{name}", data
    else:
        with open(full, "rb") as f:
            yield rel, f.read()


# =========================================================================== CSV records

def csv_records(root, rel, rec, corpus):
    """One document per CSV row. Column options are documented in corpora/_template.toml."""
    kw = dict(delimiter=rec.get("delimiter", ","), quotechar=rec.get("quotechar", '"'),
              doublequote=rec.get("doublequote", True), escapechar=rec.get("escapechar") or None)
    limit = rec.get("limit", 0)
    with open(os.path.join(root, rel), encoding=rec.get("encoding", "utf-8"), errors="replace", newline="") as f:
        reader = csv.reader(f, **kw)
        header = rec.get("columns")
        if rec.get("header", True):
            first = next(reader, None)
            header = header or first
        if not header:
            raise ValueError(f"{rel}: no header row and no `columns` list in the config")
        for i, values in enumerate(reader, 1):
            if limit and i > limit:
                break
            yield row_doc(rel, i, dict(zip(header, values)), header, rec, corpus)


# =========================================================================== SQL dumps

def _sql_values(s, i):
    """Parse one parenthesised VALUES tuple starting at s[i] == '('. Returns (values, next index)."""
    vals, i, n = [], i + 1, len(s)
    while i < n:
        c = s[i]
        if c in " \t\r\n,":
            i += 1
        elif c == ")":
            return vals, i + 1
        elif c in "'\"":
            q, buf, i = c, [], i + 1
            while i < n:
                ch = s[i]
                if ch == "\\" and i + 1 < n:
                    nxt = s[i + 1]
                    buf.append({"n": "\n", "r": "\r", "t": "\t", "0": "\0"}.get(nxt, nxt))
                    i += 2
                elif ch == q:
                    if i + 1 < n and s[i + 1] == q:      # '' inside a string
                        buf.append(q)
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    buf.append(ch)
                    i += 1
            vals.append("".join(buf))
        else:
            j = i
            while j < n and s[j] not in ",)":
                j += 1
            tok = s[i:j].strip()
            vals.append(None if tok.upper() == "NULL" else tok)
            i = j
    raise ValueError("unterminated VALUES tuple")


_INSERT = re.compile(r"INSERT\s+INTO\s+[`\"]?([\w.]+)[`\"]?\s*(?:\(([^)]*)\))?\s*VALUES\s*", re.I)


def sql_records(root, rel, rec, corpus):
    """One document per row of `INSERT INTO <table> ... VALUES (...)` statements in a SQL dump
    (.sql, or inside .7z/.zip/.tar). Options: table, columns (when the INSERTs name none), plus the
    usual id/title/date/text/fields/entities mapping; html_unescape for double-escaped text."""
    want = rec.get("table")
    limit, n = rec.get("limit", 0), 0
    for name, data in _sources(root, rel, [".sql"]):
        s = data.decode(rec.get("encoding", "utf-8"), "replace")
        for m in _INSERT.finditer(s):
            table = m.group(1).split(".")[-1]
            if want and table != want:
                continue
            cols = [c.strip(" `\"") for c in m.group(2).split(",")] if m.group(2) else rec.get("columns")
            if not cols:
                raise ValueError(f"{name}: INSERT without column names and no `columns` in the config")
            i = m.end()
            while i < len(s) and s[i] == "(":
                vals, i = _sql_values(s, i)
                row = dict(zip(cols, vals))
                if rec.get("html_unescape"):
                    for k, v in row.items():
                        if v:
                            for _ in range(3):
                                u = html.unescape(v)
                                if u == v:
                                    break
                                v = u
                            row[k] = v
                n += 1
                yield row_doc(name, n, row, cols, rec, corpus)
                if limit and n >= limit:
                    return
                while i < len(s) and s[i] in " \t\r\n,":
                    i += 1


# =========================================================================== chat logs (JSON)

FROM_KEYS = ("from", "sender", "author", "user_profile", "user", "username", "from_name", "speaker", "nick", "actor")
TO_KEYS = ("to", "recipient", "receiver", "target")
CHAT_KEYS = ("chat", "channel", "room", "conversation", "group", "thread", "chat_name")
TIME_KEYS = ("ts", "timestamp", "date", "datetime", "time", "created_at", "sent_at", "date_unixtime")
TEXT_KEYS = ("body", "text", "message", "content", "msg")


def _who(v):
    if isinstance(v, dict):
        return v.get("real_name") or v.get("name") or v.get("username") or v.get("display_name") or v.get("id") or ""
    return "" if v is None else str(v)


def _flat_text(v):
    if isinstance(v, list):    # Telegram: ["plain", {"type": "bold", "text": "x"}, ...]
        return "".join(x if isinstance(x, str) else str(x.get("text", "")) for x in v)
    return "" if v is None else (v if isinstance(v, str) else str(v))


def _when(v):
    if v in (None, ""):
        return None
    try:
        if isinstance(v, (int, float)) or re.fullmatch(r"\d{9,13}(\.\d+)?", str(v)):
            t = float(v)
            return datetime.datetime.fromtimestamp(t / 1000 if t > 1e11 else t, datetime.timezone.utc).replace(tzinfo=None)
        s = str(v).strip().replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(s).replace(tzinfo=None)
    except (ValueError, OverflowError, OSError):
        return None


def _first_key(d, keys):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _json_values(text):
    """Whole-file JSON, JSON Lines, or JSON objects simply concatenated (the Conti logs)."""
    text = text.lstrip("﻿")
    try:
        yield json.loads(text)
        return
    except json.JSONDecodeError:
        pass
    dec, i, n = json.JSONDecoder(), 0, len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n,":
            i += 1
        if i >= n:
            break
        try:
            v, i = dec.raw_decode(text, i)
        except json.JSONDecodeError:
            nl = text.find("\n", i)          # skip a broken line and carry on
            if nl < 0:
                break
            i = nl + 1
            continue
        yield v


def _messages(value, default_chat):
    """Normalise any supported chat JSON into (datetime, sender, recipient, chat, text) tuples."""
    if isinstance(value, dict) and isinstance(value.get("chats"), dict):       # Telegram full export
        for ch in value["chats"].get("list", []):
            yield from _messages(ch, default_chat)
        return
    if isinstance(value, dict) and isinstance(value.get("messages"), list):    # Telegram chat / Discord export
        chat = value.get("name") or _who(value.get("channel")) or default_chat
        for m in value["messages"]:
            if isinstance(m, dict) and m.get("type", "message") in ("message", "Default", "Reply", 0, 19):
                yield from _messages(dict(m, chat=chat), chat)
        return
    if isinstance(value, list):                                                # Slack day file / list of messages
        for m in value:
            yield from _messages(m, default_chat)
        return
    if not isinstance(value, dict):
        return
    dt = _when(_first_key(value, TIME_KEYS))
    text = _flat_text(_first_key(value, TEXT_KEYS))
    if dt is None or not text.strip():
        return
    sender = _who(_first_key(value, FROM_KEYS))
    recipient = _who(_first_key(value, TO_KEYS))
    chat = _who(_first_key(value, CHAT_KEYS)) or ("" if recipient else default_chat)
    yield dt, sender, recipient, chat, text


def _participant(name):
    from lib.formats import correspondent
    if "@" in name or name.startswith("+") or name.isdigit():
        return {"type": "identifier", "name": name.lower(), "source": "metadata", "description": "Chat account."}
    ref = correspondent(name, "")
    if ref:
        ref["description"] = "Chat participant."
        return ref
    return {"type": "identifier", "name": name, "source": "metadata", "description": "Chat account."}


def chat_records(root, rel, rec, corpus):
    """Chat logs -> one document per conversation per day (split after max_messages messages).
    Direct messages (sender and recipient) also become 'messaged' relations."""
    exts = rec.get("member_extensions", [".json", ".jsonl", ".txt"])
    max_msgs = rec.get("max_messages", 400)
    limit = rec.get("limit", 0)
    convs = {}
    for name, data in _sources(root, rel, exts):
        stem = os.path.splitext(os.path.basename(name))[0]
        parent = os.path.basename(os.path.dirname(name.split("!/")[-1]))
        default_chat = parent if re.fullmatch(r"\d{4}-\d{2}-\d{2}", stem) and parent else stem   # Slack: channel/2020-01-01.json
        for value in _json_values(data.decode("utf-8", "replace")):
            for dt, sender, recipient, chat, text in _messages(value, default_chat):
                key = chat or " ↔ ".join(sorted(x for x in (sender, recipient) if x)) or "(unknown)"
                convs.setdefault((key, dt.date().isoformat()), []).append((dt, sender, recipient, chat, text))
    d = corpus.dates
    n = 0
    for (key, day), msgs in sorted(convs.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        msgs.sort(key=lambda m: m[0])
        for part, start in enumerate(range(0, len(msgs), max_msgs), 1):
            chunk = msgs[start:start + max_msgs]
            direct = all(m[2] and not m[3] for m in chunk)
            lines = [f"[{m[0]:%H:%M:%S}] {m[1]}{' → ' + m[2] if direct else ''}: {m[4]}" for m in chunk]
            safe = re.sub(r"[#/\\]", "_", key)[:120]
            relpath = f"{rel}#{safe}/{day}" + (f"/{part}" if len(msgs) > max_msgs else "")
            people = sorted({x for m in chunk for x in (m[1], m[2]) if x})
            refs = {p: _participant(p) for p in people}
            text = "\n".join(lines)
            year = int(day[:4])
            yield {
                "id": doc_id_for(relpath), "relpath": relpath, "kind": "chat", "src": {"record": rel, "row": n + 1},
                "sources": [rel], "sha1": doc_id_for(relpath + "\0" + text), "collection": rec.get("name") or key,
                "pages": [{"n": i, "text": t, "ocr": False} for i, t in enumerate(paginate(text, corpus.extract["text_page_chars"]), 1)],
                "meta": {"title": f"{key} — {day}" + (f" (part {part})" if len(msgs) > max_msgs else ""),
                         "date": day if d["min_year"] <= year <= d["max_year"] else "", "date_source": "chat timestamp",
                         "origin": rec.get("origin", "Chat log"), "author": ", ".join(people[:3])[:200]},
                "fields": {"Conversation": key, "Messages": str(len(chunk)), "Participants": ", ".join(people[:20]),
                           "From": f"{chunk[0][0]:%Y-%m-%d %H:%M}", "To": f"{chunk[-1][0]:%Y-%m-%d %H:%M}"},
                "entities": list(refs.values()),
                "relations": [[refs[a], "messaged", refs[b]] for a, b in sorted({(m[1], m[2]) for m in chunk
                                                                                 if m[1] and m[2] and not m[3] and m[1] != m[2]})],
            }
            n += 1
            if limit and n >= limit:
                return


# =========================================================================== ICIJ Offshore Leaks

ICIJ_FILES = {  # file stem -> (node label, default entity type)
    "nodes-entities": ("Offshore entity", "company"),
    "nodes-officers": ("Officer", "person"),
    "nodes-intermediaries": ("Intermediary", "company"),
    "nodes-addresses": ("Address", "identifier"),
    "nodes-others": ("Other", "organization"),
}


def _pick(row, *names):
    for n in names:
        v = row.get(n)
        if v not in (None, ""):
            return v
    return ""


def _etype(label, default, name):
    if label == "Officer":
        if looks_like_company(name):
            return "company"
        return "person"
    if label == "Intermediary" and not looks_like_company(name) and normalize_person(name.title()):
        return "person"
    return default


def icij_records(root, rel, rec, corpus):
    folder = os.path.join(root, rel)
    want = [s.lower() for s in rec.get("sources", [])]
    limit = rec.get("limit", 0)
    nodes = {}
    for stem, (label, default) in ICIJ_FILES.items():
        path = next(iter(sorted(glob.glob(os.path.join(folder, f"*{stem}*.csv")))), None)
        if not path:
            continue
        with open(path, encoding="utf-8", errors="replace", newline="") as f:
            for row in csv.DictReader(f):
                src = _pick(row, "sourceID", "source_id", "source")
                if want and not any(w in src.lower() for w in want):
                    continue
                nid = _pick(row, "node_id", "n.node_id", "_id")
                name = norm_ws(_pick(row, "name", "n.name") if label != "Address" else
                               _pick(row, "address", "name", "n.address"))
                if not nid or not name:
                    continue
                nodes[nid] = (label, _etype(label, default, name), name, src, row)
                if limit and len(nodes) >= limit:
                    break
    rel_path = next(iter(sorted(glob.glob(os.path.join(folder, "*relationships*.csv")) +
                                glob.glob(os.path.join(folder, "*edges*.csv")))), None)
    out_edges, in_edges = {}, {}
    if rel_path:
        with open(rel_path, encoding="utf-8", errors="replace", newline="") as f:
            for row in csv.DictReader(f):
                a = _pick(row, "node_id_start", "node_1", "START_ID", ":START_ID")
                b = _pick(row, "node_id_end", "node_2", "END_ID", ":END_ID")
                if a not in nodes or b not in nodes:
                    continue
                label = norm_ws(_pick(row, "link", "rel_type", "TYPE", ":TYPE").replace("_", " ")).lower() or "related to"
                span = (_pick(row, "start_date"), _pick(row, "end_date"))
                out_edges.setdefault(a, []).append((label, b, span))
                in_edges.setdefault(b, []).append((label, a, span))

    def ref(nid):
        label, etype, name, src, _ = nodes[nid]
        return {"type": etype, "name": name, "key": f"{etype}:icij:{nid}", "source": "metadata",
                "description": f"{label} in the ICIJ Offshore Leaks database ({src or 'unknown leak'}), node {nid}."}

    d = corpus.dates
    for nid, (label, etype, name, src, row) in nodes.items():
        relpath = f"{rel}#node-{nid}"
        lines = [name, f"Type: {label}"]
        fields = {"ICIJ node": nid, "Leak": src, "Link": f"https://offshoreleaks.icij.org/nodes/{nid}"}
        for title, cols in (("Jurisdiction", ("jurisdiction_description", "jurisdiction")),
                            ("Company type", ("company_type",)), ("Incorporated", ("incorporation_date",)),
                            ("Inactivated", ("inactivation_date",)), ("Struck off", ("struck_off_date",)),
                            ("Status", ("status",)), ("Service provider", ("service_provider",)),
                            ("Countries", ("countries",)), ("Address", ("address",) if label != "Address" else ()),
                            ("Former name", ("former_name",)), ("Original name", ("original_name",)),
                            ("Note", ("note",)), ("Data valid until", ("valid_until",))):
            v = norm_ws(_pick(row, *cols)) if cols else ""
            if v:
                lines.append(f"{title}: {v}")
                fields[title] = v
        lines.append(f"Source: {src or 'ICIJ Offshore Leaks'} (ICIJ Offshore Leaks database), node {nid}")
        conn = []
        for label_, other, span in out_edges.get(nid, [])[:500]:
            conn.append(f"- {label_} → {nodes[other][2]} ({nodes[other][0].lower()}){_span(span)}")
        for label_, other, span in in_edges.get(nid, [])[:500]:
            conn.append(f"- ← {label_}: {nodes[other][2]} ({nodes[other][0].lower()}){_span(span)}")
        if conn:
            lines += ["", "Connections:"] + conn
        text = "\n".join(lines)
        me = ref(nid)
        # mention at most 100 neighbours (an address can be shared by thousands of companies);
        # every relationship is still recorded as a relation below and listed in the text
        neighbours = [ref(o) for _, o, _ in (out_edges.get(nid, []) + in_edges.get(nid, []))[:100]]
        date = parse_date(_pick(row, "incorporation_date"), None, d["min_year"], d["max_year"], 2000)
        yield {
            "id": doc_id_for(relpath), "relpath": relpath, "kind": "record", "src": {"record": rel, "node": nid},
            "sources": [rel], "sha1": doc_id_for(relpath + "\0" + text), "collection": src or "ICIJ Offshore Leaks",
            "pages": [{"n": n, "text": t, "ocr": False} for n, t in enumerate(paginate(text, corpus.extract["text_page_chars"]), 1)],
            "meta": {"title": name[:200], "date": date, "date_source": "incorporation date (registry)" if date else "",
                     "origin": "ICIJ Offshore Leaks database"},
            "fields": fields, "entities": [me] + neighbours,
            "relations": [[me, label_, ref(o)] for label_, o, _ in out_edges.get(nid, [])],
        }


def _span(span):
    a, b = span
    if a or b:
        return f" [{a or '?'} – {b or ''}]".rstrip(" ]") + "]"
    return ""


ADAPTERS = {"csv": csv_records, "sql": sql_records, "chat": chat_records, "icij": icij_records}
