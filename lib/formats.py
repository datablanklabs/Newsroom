"""
Format readers: turn the bytes of one file into pages of text.

Each reader returns an Extract: pages ([{"n", "text", "ocr"}]), OCR jobs ([(page_no, ref)]) for
pages whose text must come from Tesseract, and optional structured metadata (email headers ...).
Nothing here executes or writes the input; Office/ODF files are parsed as zip + XML with the
standard library, legacy .doc/.rtf go through macOS `textutil`, .xls needs the optional `xlrd`.
"""
import csv
import email
import email.policy
import email.utils
import hashlib
import html
import io
import os
import re
import shutil
import subprocess
import zipfile
from xml.etree import ElementTree as ET

from lib.text import display_name_to_person

EXT_FORMAT = {
    ".pdf": "pdf",
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".gif": "image", ".tif": "image", ".tiff": "image", ".bmp": "image",
    ".html": "html", ".htm": "html", ".xhtml": "html",
    ".txt": "text", ".log": "text", ".md": "text",
    ".eml": "email", ".emlx": "email", ".mbox": "mbox", ".msg": "msg",
    ".docx": "docx", ".docm": "docx", ".pptx": "pptx", ".pptm": "pptx", ".xlsx": "xlsx", ".xlsm": "xlsx",
    ".odt": "odf", ".ods": "odf", ".odp": "odf",
    ".rtf": "rtf", ".doc": "doc", ".xls": "xls",
    ".csv": "csv", ".tsv": "csv",
}


def format_of(name):
    return EXT_FORMAT.get(os.path.splitext(name)[1].lower())


class Extract:
    def __init__(self):
        self.pages = []        # [{"n", "text", "ocr"}]
        self.jobs = []         # [(page_no, ref)]  ref: {"pdf": src, "page": i} | {"image": src}
        self.pdf_meta = None
        self.meta = {}         # overrides: title, date, date_source, author, origin, classification
        self.fields = {}       # structured metadata shown on the document page
        self.entities = []     # entity refs {"type", "name", "aliases"?, "description"?}
        self.relations = []    # [src ref, relation type, dst ref]
        self.attachments = []  # names of attachments read
        self.error = None

    def add_page(self, text, ocr=False):
        self.pages.append({"n": len(self.pages) + 1, "text": text, "ocr": ocr})
        return len(self.pages)

    def to_doc(self, doc):
        doc["pages"] = self.pages
        if self.pdf_meta is not None:
            doc["pdf_meta"] = self.pdf_meta
        for k in ("meta", "fields", "entities", "relations", "attachments"):
            v = getattr(self, k)
            if v:
                doc[k] = v
        if self.error:
            doc["error"] = self.error
        return doc


# --------------------------------------------------------------------------- text helpers

def decode_text(data, fallback="utf-8"):
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        txt = data.decode("utf-16", "replace")
    else:
        try:
            txt = data.decode("utf-8")
        except UnicodeDecodeError:
            txt = data.decode(fallback, "replace")
    return txt.replace("\r\n", "\n").replace("\r", "\n")   # what open() in text mode does


_CHARSET = re.compile(rb"""<meta[^>]+charset=["']?([A-Za-z0-9_\-]+)|<\?xml[^>]+encoding=["']([A-Za-z0-9_\-]+)""", re.I)


def decode_html(data, fallback="utf-8"):
    """Honour the charset a page declares (old non-UTF-8 sites: windows-1255, koi8-r, shift_jis ...)."""
    m = _CHARSET.search(data[:4096])
    cs = (m.group(1) or m.group(2)).decode("ascii", "ignore").lower() if m else ""
    if cs and cs not in ("utf-8", "utf8"):
        try:
            return data.decode(cs, "replace").replace("\r\n", "\n").replace("\r", "\n")
        except LookupError:
            pass
    return decode_text(data, fallback)


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</h\d>|</li>|</tr>", "\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"[ \t\r\f\v]+", " ", raw)
    return re.sub(r"\n\s*\n+", "\n\n", raw).strip()


def paginate(text, size):
    """Split long text into pseudo-pages: form feeds first, then paragraph boundaries near `size` chars."""
    if not size or len(text) <= size:
        return [text]
    out = []
    for block in text.split("\f"):
        buf = ""
        for para in re.split(r"(\n\s*\n)", block):
            if len(buf) + len(para) > size and buf.strip():
                out.append(buf)
                buf = ""
            while len(para) > size:            # one enormous paragraph: cut at whitespace
                cut = para.rfind(" ", 0, size)
                cut = cut if cut > size // 2 else size
                out.append(para[:cut])
                para = para[cut:]
            buf += para
        if buf.strip():
            out.append(buf)
    return [p.strip() for p in out if p.strip()] or [""]


def looks_like_html(head: bytes):
    head = head[:2048].lower()
    return b"<html" in head or b"<!doctype html" in head


# --------------------------------------------------------------------------- PDF / images

def pdf_extract(ex, data_or_path, src, ocr_min_chars=200):
    import pymupdf
    pdf = pymupdf.open(data_or_path) if isinstance(data_or_path, str) else pymupdf.open(stream=data_or_path, filetype="pdf")
    if ex.pdf_meta is None:
        ex.pdf_meta = {k: v for k, v in (pdf.metadata or {}).items() if v}
    for i, page in enumerate(pdf):
        txt = page.get_text("text", sort=True).strip()
        needs = len(txt) < ocr_min_chars and (len(txt) < 30 or page.get_images(full=False))
        n = ex.add_page(txt)
        if needs:
            ex.jobs.append((n, {"pdf": src, "page": i + 1}))
    return ex


def render_page_png(page):
    import pymupdf
    w, h = page.rect.width, page.rect.height
    zoom = min(200 / 72, 4200 / max(w, h, 1))   # ~200 dpi, capped for poster-sized pages
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY, alpha=False)
    return pix.tobytes("png")


def image_for_ocr(data, name):
    """Tesseract reads PNG/JPEG/TIFF; convert GIF/BMP first."""
    if name.lower().endswith((".gif", ".bmp")):
        import pymupdf
        return pymupdf.Pixmap(data).tobytes("png")
    return data


# --------------------------------------------------------------------------- Office Open XML / ODF

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _xml(z, name):
    try:
        return ET.fromstring(z.read(name))
    except KeyError:
        return None


def docx_text_pages(z):
    """Word paragraphs; page breaks from Word's last rendering (w:lastRenderedPageBreak) or explicit breaks."""
    pages, cur = [], []
    parts = ["word/document.xml"] + sorted(n for n in z.namelist() if re.match(r"word/(footnotes|endnotes)\.xml$", n))
    for part in parts:
        root = _xml(z, part)
        if root is None:
            continue
        for p in root.iter(W + "p"):
            buf = []
            for el in p.iter():
                tag = el.tag
                if tag == W + "t" and el.text:
                    buf.append(el.text)
                elif tag == W + "tab":
                    buf.append("\t")
                elif tag == W + "br" and el.get(W + "type") != "page":
                    buf.append("\n")
                elif tag == W + "lastRenderedPageBreak" or (tag == W + "br" and el.get(W + "type") == "page"):
                    if cur or buf:
                        cur.append("".join(buf))
                        buf = []
                        pages.append("\n".join(cur).strip())
                        cur = []
            cur.append("".join(buf))
    if cur:
        pages.append("\n".join(cur).strip())
    return [p for p in pages if p] or [""]


def pptx_text_pages(z):
    def num(n):
        m = re.search(r"(\d+)\.xml$", n)
        return int(m.group(1)) if m else 0
    slides = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=num)
    pages = []
    for s in slides:
        root = _xml(z, s)
        paras = ["".join(t.text or "" for t in p.iter(A + "t")) for p in root.iter(A + "p")] if root is not None else []
        notes = _xml(z, s.replace("slides/slide", "notesSlides/notesSlide"))
        if notes is not None:
            nt = [("".join(t.text or "" for t in p.iter(A + "t"))) for p in notes.iter(A + "p")]
            nt = [x for x in nt if x.strip() and not x.strip().isdigit()]
            if nt:
                paras += ["", "[Speaker notes]"] + nt
        pages.append("\n".join(x for x in paras).strip())
    return pages or [""]


def xlsx_sheets(z, max_rows):
    """Yield (sheet name, rows as lists of strings)."""
    shared = []
    root = _xml(z, "xl/sharedStrings.xml")
    if root is not None:
        for si in root.iter(S + "si"):
            shared.append("".join(t.text or "" for t in si.iter(S + "t")))
    wb = _xml(z, "xl/workbook.xml")
    rels = _xml(z, "xl/_rels/workbook.xml.rels")
    targets = {}
    if rels is not None:
        for r in rels:
            targets[r.get("Id")] = r.get("Target", "")
    sheets = []
    if wb is not None:
        for sh in wb.iter(S + "sheet"):
            t = targets.get(sh.get(R + "id"), "")
            t = t.lstrip("/")
            path = t if t.startswith("xl/") else "xl/" + t
            sheets.append((sh.get("name") or path, path))
    if not sheets:
        sheets = [(n, n) for n in sorted(z.namelist()) if re.match(r"xl/worksheets/sheet\d+\.xml$", n)]
    for name, path in sheets:
        try:
            data = z.read(path)
        except KeyError:
            continue
        rows = []
        for _, el in ET.iterparse(io.BytesIO(data)):
            if el.tag != S + "row":
                continue
            row = []
            for c in el.iter(S + "c"):
                t, v = c.get("t"), c.find(S + "v")
                if t == "s" and v is not None and v.text and v.text.isdigit() and int(v.text) < len(shared):
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(S + "t"))
                else:
                    val = v.text if v is not None and v.text else ""
                row.append(val)
            el.clear()
            while row and not row[-1]:
                row.pop()
            if row:
                rows.append(row)
            if len(rows) >= max_rows:
                break
        yield name, rows


ODF_TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
ODF_TABLE = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
ODF_DRAW = "{urn:oasis:names:tc:opendocument:xmlns:drawing:1.0}"


def _odf_text(el):
    out = []
    for t in el.iter():
        if t.text and t.tag not in (ODF_TEXT + "s",):
            out.append(t.text)
        if t.tag == ODF_TEXT + "tab":
            out.append("\t")
        if t.tail and t is not el:
            out.append(t.tail)
    return "".join(out)


def odf_pages(z, rows_per_page, max_rows):
    root = _xml(z, "content.xml")
    if root is None:
        return [""]
    tables = list(root.iter(ODF_TABLE + "table"))
    draw_pages = list(root.iter(ODF_DRAW + "page"))
    if draw_pages:                                    # presentation: one page per slide
        return ["\n".join(_odf_text(p) for p in dp.iter(ODF_TEXT + "p")) for dp in draw_pages]
    if tables and not list(root.iter(ODF_TEXT + "h")):  # spreadsheet
        pages = []
        for tb in tables:
            rows = []
            for r in tb.iter(ODF_TABLE + "table-row"):
                cells = [_odf_text(c).strip() for c in r.iter(ODF_TABLE + "table-cell")]
                while cells and not cells[-1]:
                    cells.pop()
                if cells:
                    rows.append(cells)
                if len(rows) >= max_rows:
                    break
            pages += table_pages(tb.get(ODF_TABLE + "name", "Sheet"), rows, rows_per_page)
        return pages or [""]
    paras = [_odf_text(p) for p in root.iter() if p.tag in (ODF_TEXT + "p", ODF_TEXT + "h")]
    return ["\n".join(paras)]


def table_pages(name, rows, rows_per_page):
    """Tab-separated rows, header repeated at the top of every page."""
    if not rows:
        return []
    header, body = rows[0], rows[1:] or [[]]
    pages = []
    for i in range(0, len(body), rows_per_page):
        chunk = body[i:i + rows_per_page]
        lines = [f"[{name}]" if name else "", "\t".join(header)] + ["\t".join(r) for r in chunk if r]
        pages.append("\n".join(l for l in lines if l is not None).strip())
    return pages


# --------------------------------------------------------------------------- legacy formats

TEXTUTIL = shutil.which("textutil")


def textutil_text(data, fmt):
    if not TEXTUTIL:
        raise RuntimeError(f".{fmt} needs macOS textutil")
    out = subprocess.run([TEXTUTIL, "-convert", "txt", "-stdin", "-stdout", "-format", fmt],
                         input=data, capture_output=True, timeout=300)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode("utf-8", "replace")[:300] or f"textutil failed on .{fmt}")
    return decode_text(out.stdout)


def rtf_fallback(data):
    t = decode_text(data, "latin-1")
    t = re.sub(r"\\'[0-9a-f]{2}", " ", t)
    t = re.sub(r"\\[a-z]+-?\d* ?|[{}]", " ", t)
    return re.sub(r"[ \t]+", " ", t)


def xls_sheets(data, max_rows):
    try:
        import xlrd
    except ImportError:
        raise RuntimeError(".xls needs the optional package xlrd (pip install xlrd)")
    book = xlrd.open_workbook(file_contents=data, on_demand=True)
    for sh in book.sheets():
        rows = []
        for r in range(min(sh.nrows, max_rows)):
            row = [str(v) if v not in ("", None) else "" for v in sh.row_values(r)]
            while row and not row[-1]:
                row.pop()
            if row:
                rows.append(row)
        yield sh.name, rows


def csv_rows(data, max_rows):
    txt = decode_text(data, "latin-1")
    sample = txt[:20000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel_tab if sample.count("\t") > sample.count(",") else csv.excel
    rows = []
    for row in csv.reader(io.StringIO(txt), dialect):
        if any(c.strip() for c in row):
            rows.append([c.strip() for c in row])
        if len(rows) >= max_rows:
            break
    return rows


# --------------------------------------------------------------------------- email

def _header(msg, name):
    """A header as text; malformed headers in leaked mailboxes must not lose the whole message."""
    try:
        v = msg.get(name)
        return str(v).strip() if v is not None else ""
    except Exception:
        raw = msg._headers if hasattr(msg, "_headers") else []
        for k, v in raw:
            if k.lower() == name.lower():
                return str(v).strip()
        return ""


def _addresses(msg, *headers):
    vals = []
    for h in headers:
        try:
            vals += [str(v) for v in msg.get_all(h, [])]
        except Exception:
            v = _header(msg, h)
            if v:
                vals.append(v)
    try:
        return [(n, a) for n, a in email.utils.getaddresses(vals) if a or n]
    except Exception:
        return []


def correspondent(name, addr):
    """Entity ref for an email participant: a person when the display name is a usable name, else the address."""
    addr = (addr or "").strip().lower()
    person = display_name_to_person(name) if name else None
    if person:
        return {"type": "person", "name": person, "aliases": [addr] if addr else [], "source": "metadata",
                "description": "Email correspondent."}
    if addr and "@" in addr:
        return {"type": "identifier", "name": addr, "aliases": [], "source": "metadata", "description": "Email address."}
    return None


def unwrap_emlx(data):
    """Apple Mail .emlx: '<byte count>\\n' + RFC 822 message + plist trailer."""
    nl = data.find(b"\n", 0, 24)
    head = data[:nl].strip() if nl > 0 else b""
    if head.isdigit():
        n = int(head)
        return data[nl + 1:nl + 1 + n]
    return data


def email_extract(ex, data, cfg, read_attachment=None):
    """RFC 822 message -> page 1 headers + body, then one or more pages per readable attachment."""
    msg = email.message_from_bytes(unwrap_emlx(data), policy=email.policy.default)
    subject = _header(msg, "subject")
    date_raw = _header(msg, "date")
    frm = _addresses(msg, "from")
    to = _addresses(msg, "to")
    cc = _addresses(msg, "cc", "bcc")
    # display only; email.utils.formataddr raises on the non-ASCII addresses malformed headers produce
    fmt = lambda lst: ", ".join((f"{n} <{a}>" if n and a else (a or n)) for n, a in lst)
    ex.fields = {k: v for k, v in (("From", fmt(frm)), ("To", fmt(to)), ("Cc", fmt(cc)), ("Subject", subject),
                                   ("Date", date_raw), ("Message-ID", _header(msg, "message-id")),
                                   ("In-Reply-To", _header(msg, "in-reply-to"))) if v}
    if subject:
        ex.meta["title"] = subject[:200]
    if frm:
        ex.meta["author"] = fmt(frm)[:200]
    try:
        dt = email.utils.parsedate_to_datetime(date_raw) if date_raw else None
    except (TypeError, ValueError, IndexError):
        dt = None
    if dt:
        ex.meta["date"], ex.meta["date_source"] = dt.strftime("%Y-%m-%d"), "email header"
    ex.meta["origin"] = "Email"
    senders = [c for c in (correspondent(n, a) for n, a in frm) if c]
    recips = [c for c in (correspondent(n, a) for n, a in to + cc) if c]
    ex.entities = senders + recips
    for s in senders:
        for r in recips:
            if (s["type"], s["name"]) != (r["type"], r["name"]):
                ex.relations.append([s, "emailed", r])

    body, attachments = "", []
    try:
        plain = msg.get_body(preferencelist=("plain",))
        rich = msg.get_body(preferencelist=("html",))
    except Exception:
        plain = rich = None
    try:
        if plain is not None:
            body = plain.get_content()
        elif rich is not None:
            body = html_to_text(rich.get_content())
    except Exception:
        part = plain or rich
        try:
            body = decode_text(part.get_payload(decode=True) or b"") if part is not None else ""
        except Exception:
            body = ""
    if not body and not msg.is_multipart():
        try:
            body = decode_text(msg.get_payload(decode=True) or b"")
        except Exception:
            body = ""
    try:
        for part in msg.iter_attachments():
            if part.get_content_maintype() == "multipart":
                continue
            try:
                name = part.get_filename() or ""
            except Exception:
                name = ""
            attachments.append((name, part))
    except Exception:
        pass
    head = "\n".join(f"{k}: {v}" for k, v in ex.fields.items() if k in ("From", "To", "Cc", "Date", "Subject"))
    ex.add_page((head + "\n\n" + body.replace("\r\n", "\n")).strip())
    if attachments:
        ex.fields["Attachments"] = ", ".join(n or "(unnamed)" for n, _ in attachments)
    if not cfg.get("email_attachments", True) or read_attachment is None:
        return ex
    for name, part in attachments:
        fmt_ = format_of(name) or {"message/rfc822": "email"}.get(part.get_content_type())
        if not fmt_:
            continue
        try:
            payload = part.get_payload(decode=True)
            if payload is None and part.get_content_type() == "message/rfc822":
                payload = part.get_payload()[0].as_bytes()
        except Exception:
            continue
        if not payload or len(payload) > cfg["max_member_mb"] * 1_000_000:
            continue
        read_attachment(ex, name or "attachment", fmt_, payload)
        ex.attachments.append(name)
    return ex


def sha1(data):
    return hashlib.sha1(data).hexdigest()


# --------------------------------------------------------------------------- dispatcher

def extract_bytes(fmt, data, name, src, cfg, ex=None, stage=None, label=None):
    """Read one document's bytes into `ex` (a new Extract unless given: attachments append to their email).

    stage(data, suffix) -> src  saves bytes that OCR will need later and returns a source descriptor;
    without it, pages needing OCR get no job (used for nested content we cannot reopen).
    """
    ex = ex or Extract()
    size_page = cfg.get("text_page_chars", 12000)
    rows_pp, max_rows = cfg.get("sheet_page_rows", 200), cfg.get("max_sheet_rows", 50000)
    first = len(ex.pages)
    if label:
        ex.add_page(f"[Attachment: {label}]")
    try:
        if fmt == "pdf":
            if label:      # attachment: needs its own source for OCR
                n0 = len(ex.pages)
                tmp = Extract()
                pdf_src = None
                pdf_extract(tmp, data, None, cfg.get("ocr_min_chars", 200))
                if tmp.jobs and stage:
                    pdf_src = stage(data, ".pdf")
                for p in tmp.pages:
                    ex.add_page(p["text"])
                for n, ref in tmp.jobs:
                    if pdf_src:
                        ex.jobs.append((n0 + n, {"pdf": pdf_src, "page": ref["page"]}))
            else:
                pdf_extract(ex, data, src, cfg.get("ocr_min_chars", 200))
        elif fmt == "image":
            n = ex.add_page("", ocr=True)
            img_src = src if (src is not None and not label) else None
            if img_src is None and stage:              # attachment or streamed member: keep a copy for OCR
                img_src = stage(data, os.path.splitext(name)[1].lower() or ".img")
            if img_src:
                ex.jobs.append((n, {"image": img_src}))
        elif fmt == "html":
            for t in paginate(html_to_text(decode_html(data, cfg.get("encoding_fallback", "utf-8"))), size_page):
                ex.add_page(t)
        elif fmt == "text":
            for t in paginate(decode_text(data, cfg.get("encoding_fallback", "utf-8")), size_page):
                ex.add_page(t)
        elif fmt == "email":
            if label:   # forwarded message as attachment: append its text only
                sub = email_extract(Extract(), data, dict(cfg, email_attachments=False))
                for p in sub.pages:
                    ex.add_page(p["text"])
            else:
                email_extract(ex, data, cfg, read_attachment=lambda e, n, f, d: extract_bytes(f, d, n, None, cfg, e, stage, n))
        elif fmt == "msg":
            if data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":   # not Outlook (OLE2): plain RFC 822 named .msg
                return extract_bytes("email", data, name, src, cfg, ex, stage, None)
            msg_extract(ex, data, cfg)
        elif fmt == "docx":
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for p in docx_text_pages(z):
                    for t in paginate(p, size_page):
                        ex.add_page(t)
        elif fmt == "pptx":
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for t in pptx_text_pages(z):
                    ex.add_page(t)
        elif fmt == "xlsx":
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for sheet, rows in xlsx_sheets(z, max_rows):
                    for t in table_pages(sheet, rows, rows_pp):
                        ex.add_page(t)
        elif fmt == "odf":
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for p in odf_pages(z, rows_pp, max_rows):
                    for t in paginate(p, size_page):
                        ex.add_page(t)
        elif fmt == "rtf":
            txt = textutil_text(data, "rtf") if TEXTUTIL else rtf_fallback(data)
            for t in paginate(txt, size_page):
                ex.add_page(t)
        elif fmt == "doc":
            if data[:4] == b"PK\x03\x04":           # a .docx with the wrong extension
                return extract_bytes("docx", data, name, src, cfg, ex, stage, None)
            if data[:5] == b"{\\rtf":
                return extract_bytes("rtf", data, name, src, cfg, ex, stage, None)
            for t in paginate(textutil_text(data, "doc"), size_page):
                ex.add_page(t)
        elif fmt == "xls":
            if data[:4] == b"PK\x03\x04":
                return extract_bytes("xlsx", data, name, src, cfg, ex, stage, None)
            for sheet, rows in xls_sheets(data, max_rows):
                for t in table_pages(sheet, rows, rows_pp):
                    ex.add_page(t)
        elif fmt == "csv":
            rows = csv_rows(data, max_rows)
            for t in table_pages("", rows, rows_pp):
                ex.add_page(t)
        else:
            raise RuntimeError(f"unsupported format {fmt}")
    except Exception as e:
        if label:
            ex.pages[first]["text"] += f" (could not read: {type(e).__name__})"
        else:
            ex.error = repr(e)[:500]
    if not ex.pages:
        ex.add_page("")
    return ex


def msg_extract(ex, data, cfg):
    """Outlook .msg (needs the optional package extract-msg)."""
    try:
        import extract_msg
    except ImportError:
        raise RuntimeError(".msg needs the optional package extract-msg (pip install extract-msg)")
    m = extract_msg.Message(io.BytesIO(data))
    try:
        frm, to, cc = m.sender or "", m.to or "", m.cc or ""
        subject, body, date = m.subject or "", m.body or "", m.date
        ex.fields = {k: v for k, v in (("From", frm), ("To", to), ("Cc", cc), ("Subject", subject),
                                       ("Date", str(date or ""))) if v}
        if subject:
            ex.meta["title"] = subject[:200]
        if frm:
            ex.meta["author"] = frm[:200]
        if date is not None and hasattr(date, "strftime"):
            ex.meta["date"], ex.meta["date_source"] = date.strftime("%Y-%m-%d"), "email header"
        ex.meta["origin"] = "Email"
        senders = [c for c in (correspondent(n, a) for n, a in email.utils.getaddresses([frm])) if c]
        recips = [c for c in (correspondent(n, a) for n, a in email.utils.getaddresses([to, cc])) if c]
        ex.entities = senders + recips
        ex.relations = [[s, "emailed", r] for s in senders for r in recips if s["name"] != r["name"]]
        head = "\n".join(f"{k}: {v}" for k, v in ex.fields.items())
        ex.add_page((head + "\n\n" + body).strip())
    finally:
        m.close()
