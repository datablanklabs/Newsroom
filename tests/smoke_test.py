"""
End-to-end smoke test: builds a tiny synthetic corpus covering every reader and adapter, runs
build/extract.py and build/index.py on it, checks the index, then requests every app route.

    .venv/bin/python tests/smoke_test.py            (add --keep to leave the temp folder behind)

Needs the project dependencies (pymupdf, flask). Tesseract is used if installed (OCR check);
spaCy is not needed (NER is switched off for speed and determinism).
"""
import email.message
import json
import mailbox
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, PROJECT)

FAILS = []


def check(cond, what):
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        FAILS.append(what)


# --------------------------------------------------------------------------- fixture

def pdf_bytes(text):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(60, 60, 540, 780), text, fontsize=11)
    return doc.tobytes()


def scan_png(text):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=900, height=500)
    page.insert_textbox(pymupdf.Rect(40, 40, 860, 460), text, fontsize=30)
    return page.get_pixmap(dpi=150).tobytes("png")


def ooxml(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)


W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def make_fixture(root):
    os.makedirs(os.path.join(root, "memos"))
    with open(os.path.join(root, "memos", "2009-03-12-merkel-memo.pdf"), "wb") as f:
        f.write(pdf_bytes("TOP SECRET//NOFORN\nMEMORANDUM FOR THE RECORD\nSUBJECT: Berlin meeting\n\n"
                          "Angela Merkel met Vladimir Putin in Berlin on 12 March 2009 to discuss Gazprom and "
                          "the Nord Stream pipeline. Sanctions and pipeline security were raised. Sanctions again. "
                          "The embargo on arms was discussed. Corruption and bribery allegations involving Gazprom "
                          "were noted; corrupt officials took kickbacks."))
    with open(os.path.join(root, "memos", "scan.png"), "wb") as f:
        f.write(scan_png("CONFIDENTIAL\nFidel Castro spoke in Havana\nabout the Bay of Pigs"))
    # Word / Excel / PowerPoint, written as raw Office Open XML
    ooxml(os.path.join(root, "memos", "report.docx"), {
        "[Content_Types].xml": "<Types/>",
        "word/document.xml": f'<w:document {W}><w:body><w:p><w:r><w:t>Report on Mossack Fonseca and the British Virgin Islands.</w:t></w:r></w:p>'
                             f'<w:p><w:r><w:br w:type="page"/><w:t>Second page: nominee directors and bearer shares.</w:t></w:r></w:p></w:body></w:document>'})
    ooxml(os.path.join(root, "memos", "ledger.xlsx"), {
        "[Content_Types].xml": "<Types/>",
        "xl/workbook.xml": f'<workbook {S} {R}><sheets><sheet name="Payments" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                      '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/sharedStrings.xml": f'<sst {S}><si><t>Payee</t></si><si><t>Amount</t></si><si><t>Deutsche Bank</t></si></sst>',
        "xl/worksheets/sheet1.xml": f'<worksheet {S}><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
                                    f'<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2"><v>125000</v></c></row></sheetData></worksheet>'})
    ooxml(os.path.join(root, "memos", "briefing.pptx"), {
        "[Content_Types].xml": "<Types/>",
        "ppt/slides/slide1.xml": f'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" {A}><a:p><a:r><a:t>NATO briefing on Ukraine</a:t></a:r></a:p></p:sld>',
        "ppt/slides/slide2.xml": f'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" {A}><a:p><a:r><a:t>Slide two: HIMARS deliveries</a:t></a:r></a:p></p:sld>'})
    # email with a PDF attachment, and a two-message mailbox
    os.makedirs(os.path.join(root, "mail"))
    msg = email.message.EmailMessage()
    msg["From"] = "John Podesta <john.podesta@example.org>"
    msg["To"] = "Huma Abedin <huma.abedin@example.org>"
    msg["Cc"] = "press@example.org"
    msg["Subject"] = "Wire to account GB82WEST12345698765432"
    msg["Date"] = "Mon, 07 Mar 2016 09:15:00 -0500"
    msg.set_content("Please send the transfer to GB82WEST12345698765432 and copy press@example.org.\nJohn")
    msg.add_attachment(pdf_bytes("Attachment: talking points about Bernie Sanders and the DNC."),
                       maintype="application", subtype="pdf", filename="points.pdf")
    with open(os.path.join(root, "mail", "message.eml"), "wb") as f:
        f.write(bytes(msg))
    box = mailbox.mbox(os.path.join(root, "mail", "archive.mbox"))
    for i, (frm, to) in enumerate([("Huma Abedin <huma.abedin@example.org>", "John Podesta <john.podesta@example.org>"),
                                   ("John Podesta <john.podesta@example.org>", "Huma Abedin <huma.abedin@example.org>")]):
        m = email.message.EmailMessage()
        m["From"], m["To"], m["Subject"] = frm, to, f"Re: schedule {i}"
        m["Date"] = f"Tue, 0{i + 1} Nov 2016 10:00:00 +0000"
        m.set_content(f"Meeting about Wikileaks and the account GB82WEST12345698765432, round {i}.")
        box.add(m)
    box.close()
    # Cablegate-style CSV (no header, backslash-escaped quotes)
    with open(os.path.join(root, "cables.csv"), "w", encoding="utf-8") as f:
        f.write('"1","12/28/1966 18:48","66BUENOSAIRES2481","Embassy Buenos Aires","UNCLASSIFIED","","P R 281848Z DEC 66\nFM AMEMBASSY BUENOS AIRES",'
                '"UNCLASSIFIED BUENOS AIRES 2481\n\nE.O. 12958: DECL: DECLASSIFIED BY NARA\nTAGS: EFIS, PBTS, AR\nSUBJECT:  EXTENDED NATIONAL JURISDICTIONS OVER HIGH SEAS\n\n'
                '1. PRESS REPORTS CONFIRM NEW ARGENTINE LEGISLATION ON THE \\"PREFERENTIAL JURISDICTION\\" ZONE. TURKEY AND CHILE OBJECT.\nKEEGAN"\n')
        f.write('"2","02/10/2010 12:00","10PARIS123","Embassy Paris","CONFIDENTIAL","","",'
                '"C O N F I D E N T I A L PARIS 000123\n\nTAGS: PREL, PGOV, FR, IR\nSUBJECT: SARKOZY ON IRAN SANCTIONS\n\nClassified By: Ambassador.\n'
                '1. (C) Nicolas Sarkozy told the Ambassador that sanctions on Iran must tighten.\nRIVKIN"\n')
    # ICIJ Offshore Leaks export (tiny)
    icij = os.path.join(root, "icij")
    os.makedirs(icij)
    with open(os.path.join(icij, "nodes-entities.csv"), "w") as f:
        f.write("node_id,name,jurisdiction_description,incorporation_date,status,countries,sourceID\n"
                "10000001,ALPHA HOLDINGS LIMITED,British Virgin Islands,23-MAR-2006,Active,Russia,Panama Papers\n"
                "10000002,BETA TRADING S.A.,Panama,01-JAN-2001,Defaulted,Iceland,Paradise Papers\n")
    with open(os.path.join(icij, "nodes-officers.csv"), "w") as f:
        f.write("node_id,name,countries,sourceID\n12000001,Ivan Petrovich Sidorov,Russia,Panama Papers\n")
    with open(os.path.join(icij, "nodes-addresses.csv"), "w") as f:
        f.write("node_id,address,countries,sourceID\n14000001,\"1 Main Street, Road Town, Tortola\",British Virgin Islands,Panama Papers\n")
    with open(os.path.join(icij, "relationships.csv"), "w") as f:
        f.write("node_id_start,node_id_end,rel_type,link,start_date,end_date,sourceID\n"
                "12000001,10000001,officer_of,shareholder of,2006-03-23,,Panama Papers\n"
                "10000001,14000001,registered_address,registered address,,,Panama Papers\n")
    # archives: a zip with a document and a fake executable (must never be read), and a tar.gz
    with zipfile.ZipFile(os.path.join(root, "bundle.zip"), "w") as z:
        z.writestr("inner/memo2.pdf", pdf_bytes("Second memo: Edward Snowden and the NSA in Hong Kong, June 2013."))
        z.writestr("inner/notes.txt", "Notes on GCHQ and Tempora.")
        z.writestr("inner/malware.exe", b"MZ\x90\x00 not really malware")
    data = b"<html><body><h1>Letter</h1><p>Letter from Kofi Annan to the United Nations.</p><script>alert(1)</script></body></html>"
    with tarfile.open(os.path.join(root, "letters.tar.gz"), "w:gz") as t:
        info = tarfile.TarInfo("letters/annan.html")
        info.size = len(data)
        t.addfile(info, __import__("io").BytesIO(data))
    with open(os.path.join(root, "page.html"), "w") as f:
        f.write("<html><head><title>t</title><script>evil()</script></head><body><p>The European Union and NATO met in Brussels.</p></body></html>")
    with open(os.path.join(root, "readme.txt"), "w") as f:
        f.write("Plain text about Huawei and ZTE in Beijing. " * 3)
    with open(os.path.join(root, "ignored.torrent"), "w") as f:
        f.write("d8:announce")
    # SQL dump (MySQL quoting, double-escaped HTML entities) inside a zip
    sql = ("CREATE TABLE war_diary (ReportKey varchar(255), Date varchar(255), Title text, Summary text, Region varchar(255));\n"
           "INSERT INTO war_diary (ReportKey, Date, Title, Summary, Region) VALUES "
           "('K-1', '2007-08-02 08:08:00', 'IED Explosion Kandahar', 'ANA patrol hit an IED near Kandahar; 2 WIA. It\\'s the third this week. &amp;apos;Q&amp;apos;', 'RC SOUTH'),"
           "('K-2', '2008-01-15 10:00:00', 'Escalation of force', 'Warning shots fired at a vehicle, \"no injuries\"', 'RC EAST');\n")
    with zipfile.ZipFile(os.path.join(root, "logs.sql.zip"), "w") as z:
        z.writestr("war.sql", sql)
    # chat logs: Conti-style concatenated objects, a Telegram export, a Slack channel folder
    chats = os.path.join(root, "chats")
    os.makedirs(os.path.join(chats, "slack", "general"))
    with open(os.path.join(chats, "jabber-20210129.json"), "w") as f:
        for ts, a, b, body in (("2021-01-29T00:06:46", "mango@x.onion", "stern@x.onion", "salary for the team"),
                               ("2021-01-29T04:04:39", "stern@x.onion", "mango@x.onion", "Bitcoin wallet is empty"),
                               ("2021-01-30T09:00:00", "price@x.onion", "green@x.onion", "hello")):
            f.write(json.dumps({"ts": ts, "from": a, "to": b, "body": body}, indent=2) + "\n")
    with open(os.path.join(chats, "result.json"), "w") as f:
        json.dump({"name": "Evidence Task", "type": "private_group", "messages": [
            {"id": 1, "type": "message", "date": "2025-06-16T12:00:00", "from": "Alice Cooper", "text": "Report from Gaza City"},
            {"id": 2, "type": "message", "date": "2025-06-16T12:05:00", "from": "Bob Marley",
             "text": ["see ", {"type": "link", "text": "https://example.org"}, " attached"]},
            {"id": 3, "type": "service", "date": "2025-06-16T12:06:00", "actor": "Alice Cooper", "action": "pin_message"}]}, f)
    with open(os.path.join(chats, "slack", "general", "2020-03-01.json"), "w") as f:
        json.dump([{"user_profile": {"real_name": "Carol King"}, "text": "Budget meeting moved", "ts": "1583020800.000100"}], f)


# a second corpus over part of the same files, built after the first app checks: the global views must pick it up
CONFIG2 = """
title = "Smoke test 2"
root = "{root}"
data_dir = "{data}"
packs = ["core", "government", "diplomatic"]
include = ["memos/**"]

[index]
ner = false
codenames = false
"""

CONFIG = """
title = "Smoke test"
description = "Synthetic corpus covering every reader."
root = "{root}"
data_dir = "{data}"
packs = ["core", "government", "diplomatic", "offshore", "political"]

[dates]
min_year = 1950
two_digit_century = 1900

[extract]
archives = ["zip", "tar"]
archive_members = ["pdf", "text", "html"]

[index]
ner = false
codenames = false
identifiers = ["email", "iban"]
identifier_min_docs = 1

[[records]]
type = "csv"
path = "cables.csv"
name = "Cables"
kind = "cable"
header = false
columns = ["row", "date", "ref", "origin", "classification", "references", "header", "body"]
escapechar = "\\\\"
doublequote = false
id = "ref"
title = "ref"
date = "date"
date_format = "%m/%d/%Y %H:%M"
text = ["body"]
origin = "origin"
classification = "classification"
fields = ["ref", "origin", "classification"]

[[records]]
type = "icij"
path = "icij"

[[records]]
type = "sql"
path = "logs.sql.zip"
kind = "war-log"
table = "war_diary"
html_unescape = true
id = "ReportKey"
title = "Title"
date = "Date"
text = ["Title", "Summary"]
fields = ["Region"]
entities = {{ Region = "place" }}

[[records]]
type = "chat"
path = "chats"
name = "Chats"
"""


# --------------------------------------------------------------------------- run

def main():
    keep = "--keep" in sys.argv
    tmp = tempfile.mkdtemp(prefix="newsroom-smoke-")
    root, data, corpora = (os.path.join(tmp, d) for d in ("files", "data", "corpora"))
    os.makedirs(root)
    os.makedirs(corpora)
    make_fixture(root)
    cfg = os.path.join(corpora, "smoke.toml")
    with open(cfg, "w") as f:
        f.write(CONFIG.format(root=root, data=data))
    py = sys.executable

    def build(cfg):
        for step in ("extract", "index"):
            print(f"[{step}]")
            out = subprocess.run([py, os.path.join(PROJECT, "build", f"{step}.py"), "--corpus", cfg] + (["--workers", "2"] if step == "extract" else []),
                                 capture_output=True, text=True)
            print("    " + out.stdout.strip().replace("\n", "\n    "))
            if out.returncode != 0:
                print(out.stderr)
                raise SystemExit(f"{step} failed")
    build(cfg)

    con = sqlite3.connect(os.path.join(data, "index.db"))
    con.row_factory = sqlite3.Row
    one = lambda sql, *a: con.execute(sql, a).fetchone()
    kinds = {r["kind"]: r["n"] for r in con.execute("SELECT kind, COUNT(*) n FROM documents GROUP BY kind")}
    print("[checks]", kinds)
    for k, n in (("pdf", 2), ("image", 1), ("docx", 1), ("xlsx", 1), ("pptx", 1), ("email", 3), ("cable", 2),
                 ("record", 4), ("html", 2), ("text", 2), ("war-log", 2), ("chat", 4)):
        check(kinds.get(k, 0) == n, f"{n} {k} document(s) (got {kinds.get(k, 0)})")
    check(one("SELECT COUNT(*) c FROM documents WHERE relpath LIKE '%malware.exe%'")["c"] == 0, "executable inside zip was never read")
    check(one("SELECT COUNT(*) c FROM documents WHERE relpath LIKE '%.torrent'")["c"] == 0, "unsupported files skipped")
    page = lambda rel: " ".join(r["text"] for r in con.execute(
        "SELECT p.text FROM pages p JOIN documents d ON d.id=p.doc_id WHERE d.relpath LIKE ? ORDER BY p.page_no", (rel,)))
    check("bearer shares" in page("%report.docx") and one("SELECT pages FROM documents WHERE relpath LIKE '%report.docx'")["pages"] == 2,
          "docx text with its page break")
    check("Deutsche Bank" in page("%ledger.xlsx") and "125000" in page("%ledger.xlsx"), "xlsx shared strings and numbers")
    check("HIMARS" in page("%briefing.pptx"), "pptx slides")
    check("talking points" in page("%message.eml"), "email attachment text extracted")
    check("<script>" not in page("page.html") and "evil" not in page("page.html"), "scripts stripped from HTML")
    check("Kofi Annan" in page("letters.tar.gz!/%"), "tar.gz member read")
    check("Snowden" in page("bundle.zip!/%memo2.pdf"), "zip member read in memory")
    if shutil.which("tesseract") or os.path.exists("/opt/homebrew/bin/tesseract"):
        check("Castro" in page("%scan.png"), "OCR of a scanned image")
    d = one("SELECT * FROM documents WHERE relpath LIKE '%merkel-memo.pdf'")
    check(d["doc_date"] == "2009-03-12" and d["classification"] == "TOP SECRET", f"filename date + classification ({d['doc_date']}, {d['classification']})")
    e = one("SELECT * FROM documents WHERE relpath LIKE '%message.eml'")
    check(e["doc_date"] == "2016-03-07" and e["title"].startswith("Wire to account") and "Podesta" in e["author"], "email headers -> date, title, author")
    c = one("SELECT * FROM documents WHERE relpath LIKE 'cables.csv#66BUENOSAIRES2481'")
    check(c is not None and c["title"].startswith("Extended National Jurisdictions") and c["origin"] == "Embassy Buenos Aires"
          and c["doc_date"] == "1966-12-28", f"cable header parsed ({c and c['title']!r})")
    check('"PREFERENTIAL JURISDICTION"' in page("cables.csv#66BUENOSAIRES2481"), "backslash-escaped quotes in CSV")
    ent = lambda key: one("SELECT * FROM entities WHERE key=?", key)
    for key in ("person:Angela Merkel", "person:Vladimir Putin", "place:Berlin", "company:Gazprom", "company:Mossack Fonseca",
                "place:British Virgin Islands", "idea:Corruption & bribery", "idea:Sanctions & embargoes", "person:John Podesta", "person:Huma Abedin",
                "person:Nicolas Sarkozy", "idea:PREL — External political relations", "place:Argentina", "place:Turkey",
                "identifier:GB82WEST12345698765432", "identifier:press@example.org", "organization:NATO", "person:Edward Snowden"):
        check(ent(key) is not None, f"entity {key}")
    check(ent("person:John Podesta") is not None and "john.podesta@example.org" in ent("person:John Podesta")["aliases"],
          "email address recorded as an alias of its correspondent")
    rel = lambda a, t, b: one("""SELECT r.docs FROM relations r JOIN entities x ON x.id=r.src JOIN entities y ON y.id=r.dst
                                 WHERE x.key=? AND r.type=? AND y.key=?""", a, t, b)
    r = rel("person:John Podesta", "emailed", "person:Huma Abedin")
    check(r is not None and r["docs"] == 2, f"emailed relation counted over messages ({r and r['docs']})")
    check(rel("person:Ivan Petrovich Sidorov", "shareholder of", "company:ALPHA HOLDINGS LIMITED") is None, "ICIJ keys are node-specific")
    icij = one("""SELECT COUNT(*) c FROM relations r JOIN entities x ON x.id=r.src WHERE r.type='shareholder of' AND x.name='Ivan Petrovich Sidorov'""")
    check(icij["c"] == 1, "ICIJ officer -> company relation")
    check(one("SELECT COUNT(*) c FROM edges")["c"] > 0, "co-occurrence edges")
    w = one("SELECT * FROM documents WHERE relpath LIKE 'logs.sql.zip!/war.sql#K-1'")
    check(w is not None and w["doc_date"] == "2007-08-02" and "It's the third" in page("logs.sql.zip!/war.sql#K-1")
          and "'Q'" in page("logs.sql.zip!/war.sql#K-1"), "SQL dump row: date, escaped quotes, double-escaped entities")
    check(ent("place:RC SOUTH") is not None, "SQL column mapped to an entity")
    titles = {r["title"]: r["doc_date"] for r in con.execute("SELECT title, doc_date FROM documents WHERE kind='chat'")}
    check("mango@x.onion ↔ stern@x.onion — 2021-01-29" in titles, f"Jabber conversation grouped per day ({sorted(titles)})")
    check("Evidence Task — 2025-06-16" in titles and "general — 2020-03-01" in titles, "Telegram and Slack exports")
    check("see https://example.org attached" in page("chats#Evidence Task/2025-06-16"), "Telegram rich-text messages flattened")
    check(rel("identifier:mango@x.onion", "messaged", "identifier:stern@x.onion") is not None, "chat 'messaged' relation")

    # ------------------------------------------------------------- web app
    print("[app]")
    os.environ["NEWSROOM_CORPORA"] = corpora
    os.environ["NEWSROOM_DATA"] = os.path.join(tmp, "dataroot")      # where the global index goes
    import importlib
    import lib.config
    importlib.reload(lib.config)
    sys.path.insert(0, os.path.join(PROJECT, "app"))
    import app as webapp
    client = webapp.app.test_client()
    import lib.globalindex
    rv = client.get("/search-all?q=Merkel")            # before any global index exists: answers without waiting for it
    check(rv.status_code == 200 and "Angela Merkel" in rv.get_data(as_text=True), "search-all works without the global index")
    if lib.globalindex._state["thread"] is not None:
        lib.globalindex._state["thread"].join()
    doc_ids = {r["kind"]: r["id"] for r in con.execute("SELECT kind, MIN(id) id FROM documents GROUP BY kind")}
    merkel = ent("person:Angela Merkel")["id"]
    urls = ["/", "/search-all?q=Merkel", "/search-all?q=%22bearer+shares%22", "/c/smoke/", "/c/smoke/search?q=Merkel",
            "/c/smoke/search?q=*&kind=email", "/c/smoke/search?entity=%d" % merkel, "/c/smoke/entities", "/c/smoke/entities?type=identifier",
            f"/c/smoke/entity/{merkel}", "/c/smoke/graph", "/c/smoke/timeline", "/c/smoke/api/graph",
            "/c/smoke/api/graph?source=relations&min_docs=1", f"/c/smoke/api/graph?focus={merkel}",
            f"/c/smoke/api/timeline?ids={merkel}&mode=share", "/c/smoke/api/entities?q=Mer",
            "/all/entities", "/all/entities?type=person&q=Merkel", "/all/entity?key=person%3Aangela%20merkel",
            "/all/entity?key=person%3Aangela%20merkel&with=person%3Avladimir%20putin", "/all/graph", "/all/timeline",
            "/all/api/graph", "/all/api/graph?focus=person%3Aangela%20merkel", "/all/api/graph?source=relations&min_docs=1",
            "/all/api/timeline?id=person%3Aangela%20merkel&id=place%3Aberlin&mode=share", "/all/api/entities?q=Mer"]
    urls += [f"/c/smoke/doc/{i}" for i in doc_ids.values()]
    for u in urls:
        rv = client.get(u)
        check(rv.status_code == 200, f"GET {u} -> {rv.status_code}")
    for kind, mime in (("pdf", "application/pdf"), ("image", "image/png"), ("html", "text/plain"), ("email", "text/plain")):
        rv = client.get(f"/c/smoke/file/{doc_ids[kind]}")
        check(rv.status_code == 200 and rv.mimetype == mime, f"original {kind} served as {rv.mimetype}")
    rv = client.get(f"/c/smoke/file/{doc_ids['record']}")
    check(rv.status_code == 404, "records have no original file")
    for rel_like in ("bundle.zip!/%", "letters.tar.gz!/%"):
        i = one("SELECT id FROM documents WHERE relpath LIKE ?", rel_like)["id"]
        rv = client.get(f"/c/smoke/file/{i}")
        check(rv.status_code == 200, f"archive member {rel_like} served")
    rv = client.get("/c/nope/")
    check(rv.status_code == 404, "unknown corpus -> 404")
    rels = client.get("/c/smoke/api/graph?source=relations&min_docs=1").get_json()
    check(len(rels["links"]) >= 2, f"relations graph has links ({len(rels['links'])})")
    check(client.get("/all/entity?key=nope").status_code == 404, "unknown global entity -> 404")
    check(client.get("/all/").status_code == 302, "/all/ redirects to the global entity list")
    # with one corpus built, the global ego network of its best-linked entity is that corpus's ego network
    hub = one("SELECT e.id, e.type, e.name FROM edges x JOIN entities e ON e.id = x.src GROUP BY x.src ORDER BY COUNT(*) DESC LIMIT 1")
    import urllib.parse
    from lib.globalindex import gkey
    local = client.get(f"/c/smoke/api/graph?focus={hub['id']}&min_docs=1").get_json()
    glob = client.get("/all/api/graph?min_docs=1&focus=" + urllib.parse.quote(gkey(hub["type"], hub["name"]))).get_json()
    check(sorted(n["name"] for n in glob["nodes"]) == sorted(n["name"] for n in local["nodes"]) and len(glob["links"]) == len(local["links"]),
          f"global ego network of {hub['name']} matches the corpus one ({len(glob['nodes'])} nodes, {len(glob['links'])} links)")
    grels = client.get("/all/api/graph?source=relations&min_docs=1").get_json()
    check(len(grels["links"]) == len(rels["links"]), f"global relations graph = the only corpus's ({len(grels['links'])})")

    # a second corpus appears in the global views without restarting the app
    with open(os.path.join(corpora, "smoke2.toml"), "w") as f:
        f.write(CONFIG2.format(root=root, data=os.path.join(tmp, "data2")))
    build(os.path.join(corpora, "smoke2.toml"))
    client.get("/all/entities")                       # notices the new corpus and rebuilds in the background
    t = lib.globalindex._state["thread"]
    if t is not None:
        t.join()
    merkel_all = client.get("/all/api/entities?q=Angela Merkel").get_json()
    check(merkel_all and merkel_all[0]["id"] == "person:angela merkel" and merkel_all[0]["n_corpora"] == 2,
          f"global entity merged over both corpora ({merkel_all[:1]})")
    page = client.get("/all/entity?key=person%3Aangela%20merkel").get_data(as_text=True)
    check("Smoke test 2" in page and "Smoke test" in page, "global entity page lists both corpora")
    page = client.get(f"/c/smoke/entity/{merkel}").get_data(as_text=True)
    check("Smoke test 2" in page and "across all collections" in page, "corpus entity page: 'also in' the second corpus")
    tl = client.get("/all/api/timeline?id=person%3Aangela%20merkel&mode=docs").get_json()
    check(sum(v["value"] for v in tl["series"][0]["values"]) == merkel_all[0]["doc_count"],
          "global timeline counts every dated document of both corpora")

    print(f"\n{len(FAILS)} failure(s)" + (": " + "; ".join(FAILS) if FAILS else ""))
    if keep:
        print("kept", tmp)
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
