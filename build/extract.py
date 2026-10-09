"""
Stage 1: discover every document in a corpus and extract per-page text.

  .venv/bin/python build/extract.py --corpus snowden [--workers 7] [--limit 200] [--only 'cables*'] [--force]

Formats: PDF (text layer, OCR for scanned pages), images (OCR), HTML, text, email (.eml, .mbox,
.msg), Word/PowerPoint/Excel (.docx/.pptx/.xlsx), OpenDocument, .rtf/.doc (macOS textutil),
.xls (xlrd), CSV tables. Archives: .zip read in memory; .tar/.tgz/.7z/.rar streamed when enabled
in the corpus config. Only allow-listed document formats are ever read from archives; nothing is
unpacked to disk or executed. Structured datasets ([[records]] in the config) become one document
per row (CSV) or per node (ICIJ Offshore Leaks).

Output: data/<corpus>/extracted/<doc_id>.json, or <container_id>.jsonl for archives, mailboxes and
record files. OCR results are cached in data/<corpus>/ocr/ and unchanged sources are skipped
(data/<corpus>/manifest.json), so reruns are cheap.
"""
import argparse
import collections
import fnmatch
import hashlib
import json
import mailbox
import os
import re
import sys
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, PROJECT)
from lib import archives, formats, records  # noqa: E402
from lib.config import load_corpus  # noqa: E402
from lib.ocr import ocr_image_bytes  # noqa: E402

SKIP_DIRS = {"__MACOSX", ".git", ".svn", ".hg", ".Trashes", ".Spotlight-V100", ".fseventsd", ".TemporaryItems"}
STREAMED = {"tar", "7z", "rar"}


def doc_id_for(relpath: str) -> str:
    return hashlib.sha1(relpath.encode("utf-8")).hexdigest()[:12]


def sha1_file(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _stat(path):
    st = os.stat(path)
    return [st.st_size, int(st.st_mtime)]


# =========================================================================== discovery

def discover(C):
    """Return (specs, skipped counter). A spec is one document, or one container (archive stream,
    mailbox, record file) that expands into many documents."""
    X = C.extract
    root = C.root
    formats_on = set(X["formats"])
    members_on = set(X["archive_members"])
    max_file = X["max_file_mb"] * 1_000_000
    max_member = X["max_member_mb"] * 1_000_000
    min_img = X["min_image_kb"] * 1000
    scan_re = re.compile(X["page_scan_pattern"], re.I) if X["page_scan_pattern"] else None
    specs, skipped = [], collections.Counter()
    scans = collections.defaultdict(list)

    record_paths = {}
    for i, rec in enumerate(C.records):
        for rel in records.record_files(root, rec):
            record_paths[rel] = i
            specs.append({"relpath": rel, "kind": "container", "ctype": rec.get("type", "csv"), "rec": i,
                          "src": {"file": rel}, "stat": _dirstat(os.path.join(root, rel))})

    for dirpath, dirnames, filenames in os.walk(root):
        reldir = os.path.relpath(dirpath, root)
        reldir = "" if reldir == "." else reldir
        keep = []
        for dn in sorted(dirnames):
            rd = os.path.join(reldir, dn)
            if dn in SKIP_DIRS or C.excluded_dir(rd) or rd in record_paths or not C.could_contain(rd):
                continue
            keep.append(dn)
        dirnames[:] = keep
        for fn in sorted(filenames):
            if fn.startswith("._") or fn == ".DS_Store":
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.join(reldir, fn) if reldir else fn
            if rel in record_paths or not C.wanted_file(rel):
                continue
            ext = os.path.splitext(fn)[1].lower()
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            atype = archives.archive_type(fn)
            if atype:
                if atype not in X["archives"]:
                    skipped[f"archive .{atype} (not enabled)"] += 1
                elif atype == "zip":
                    specs += _zip_specs(full, rel, members_on, max_member, min_img, skipped)
                else:
                    specs.append({"relpath": rel, "kind": "container", "ctype": atype, "src": {"file": rel},
                                  "stat": _stat(full)})
                continue
            fmt = formats.format_of(fn)
            if fmt is None and ext == "" and X["html_extensionless"] and "html" in formats_on:
                try:
                    with open(full, "rb") as f:
                        fmt = "html" if formats.looks_like_html(f.read(2048)) else None
                except OSError:
                    fmt = None
            if fmt is None or fmt not in formats_on:
                skipped[ext or "(no extension)"] += 1
                continue
            if fmt == "mbox":
                specs.append({"relpath": rel, "kind": "container", "ctype": "mbox", "src": {"file": rel}, "stat": _stat(full)})
                continue
            if size > max_file:
                skipped[f"{ext} over {X['max_file_mb']} MB"] += 1
                continue
            if fmt == "image":
                if size < min_img:
                    continue
                m = scan_re.match(fn) if scan_re else None
                if m:
                    scans[os.path.join(reldir, m.group("base"))].append((int(m.group("n")), rel))
                    continue
            specs.append({"relpath": rel, "kind": fmt, "src": {"file": rel}, "stat": [size, int(os.path.getmtime(full))]})
    for base, pages in scans.items():
        pages.sort()
        files = [p for _, p in pages]
        st = [_stat(os.path.join(root, p)) for p in files]
        specs.append({"relpath": base + " (page scans)", "kind": "image-set", "src": {"files": files},
                      "stat": [sum(s[0] for s in st), max(s[1] for s in st)]})
    for s in specs:
        s["id"] = doc_id_for(s["relpath"])
    return specs, skipped


def _dirstat(path):
    if os.path.isfile(path):
        return _stat(path)
    total, newest = 0, 0
    for dp, _, fns in os.walk(path):
        for fn in fns:
            s = _stat(os.path.join(dp, fn))
            total, newest = total + s[0], max(newest, s[1])
    return [total, newest]


def _zip_specs(full, rel, members_on, max_member, min_img, skipped):
    out = []
    try:
        members = archives.zip_members(full)
    except (zipfile.BadZipFile, OSError, ValueError) as e:
        skipped[f"unreadable zip ({type(e).__name__})"] += 1
        return out
    st = _stat(full)
    for m, size, encrypted in members:
        fmt = formats.format_of(m)
        if fmt is None or fmt not in members_on or fmt == "mbox":
            skipped["zip member " + (os.path.splitext(m)[1].lower() or "(no extension)")] += 1
            continue
        if encrypted:
            skipped["zip member (encrypted)"] += 1
            continue
        if size > max_member or (fmt == "image" and size < min_img):
            skipped["zip member (size limit)"] += 1
            continue
        out.append({"relpath": f"{rel}!/{m}", "kind": fmt, "src": {"zip": rel, "member": m}, "stat": st + [size]})
    return out


# =========================================================================== workers

C = None   # corpus config, loaded once per worker process


def _init(corpus_path):
    global C
    import pymupdf
    pymupdf.TOOLS.mupdf_display_errors(False)
    C = load_corpus(corpus_path)


def read_src(src, max_bytes=None):
    """Bytes of a source descriptor (file, zip member, staged copy, streamed archive member)."""
    if "file" in src:
        with open(os.path.join(C.root, src["file"]), "rb") as f:
            return f.read()
    if "zip" in src:
        return archives.read_zip_member(os.path.join(C.root, src["zip"]), src["member"], max_bytes)
    if "staged" in src:
        with open(os.path.join(C.staged_dir, src["staged"]), "rb") as f:
            return f.read()
    if "archive" in src:
        return archives.read_member(os.path.join(C.root, src["archive"]), src["atype"], src["member"], max_bytes)
    raise ValueError(f"cannot read {src}")


def stager(doc_id):
    """Save bytes OCR will need later (attachments, streamed archive members) under data/<corpus>/staged/."""
    def stage(data, suffix):
        name = f"{doc_id}/{hashlib.sha1(data).hexdigest()[:12]}{suffix}"
        path = os.path.join(C.staged_dir, name)
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path + ".tmp", "wb") as f:
                f.write(data)
            os.replace(path + ".tmp", path)
        return {"staged": name}
    return stage


def _base_doc(spec):
    doc = {k: spec[k] for k in ("id", "relpath", "kind", "src", "stat")}
    if "zip" in spec["src"]:
        doc["member"] = spec["src"]["member"]
        doc["sources"] = [spec["src"]["zip"]]
    elif "files" in spec["src"]:
        doc["sources"] = spec["src"]["files"]
    elif "file" in spec["src"]:
        doc["sources"] = [spec["src"]["file"]]
    return doc


def extract_one(fmt, data, name, src, doc, staged_src=None):
    """Run a reader, attach its output to doc and return OCR jobs [(doc_id, page, ref)]."""
    stage = stager(doc["id"])
    ex = formats.extract_bytes(fmt, data, name, src, C.extract, stage=stage)
    if src is None and ex.jobs:                       # streamed member: OCR needs a staged copy
        s = staged_src or stage(data, os.path.splitext(name)[1].lower())
        ex.jobs = [(n, {k: (s if v is None else v) for k, v in ref.items()}) for n, ref in ex.jobs]
    if not C.extract["ocr"]:
        ex.jobs = []
    ex.to_doc(doc)
    return [(doc["id"], n, ref) for n, ref in ex.jobs]


def stage_a(spec):
    """Extract one spec. Returns (spec relpath, [output files], [ocr jobs], note)."""
    try:
        if spec["kind"] == "container":
            return stage_a_container(spec)
        doc = _base_doc(spec)
        src, fmt = spec["src"], spec["kind"]
        jobs = []
        try:
            if fmt == "image-set":
                doc["sha1"] = sha1_file(os.path.join(C.root, src["files"][0]))
                doc["pages"] = [{"n": i + 1, "text": "", "ocr": True} for i in range(len(src["files"]))]
                if C.extract["ocr"]:
                    jobs = [(doc["id"], i + 1, {"image": {"file": f}}) for i, f in enumerate(src["files"])]
            elif fmt == "pdf" and "file" in src:      # let MuPDF read big PDFs from disk
                path = os.path.join(C.root, src["file"])
                doc["sha1"] = sha1_file(path)
                ex = formats.pdf_extract(formats.Extract(), path, src, C.extract["ocr_min_chars"])
                if C.extract.get("sidecar") == "ia-hocr":
                    apply_ia_hocr(ex, path)
                ex.to_doc(doc)
                jobs = [(doc["id"], n, ref) for n, ref in ex.jobs] if C.extract["ocr"] else []
            else:
                data = read_src(src, C.extract["max_member_mb"] * 1_000_000 if "zip" in src else None)
                doc["sha1"] = hashlib.sha1(data).hexdigest()
                jobs = extract_one(fmt, data, os.path.basename(spec["relpath"]), src, doc)
        except Exception as e:  # keep going; record the error
            doc["error"] = repr(e)[:500]
            doc.setdefault("pages", [])
        out = spec["id"] + ".json"
        _write_json(os.path.join(C.extracted_dir, out), doc)
        return spec["relpath"], [out], jobs, ""
    except Exception as e:
        return spec["relpath"], [], [], f"failed: {e!r}"[:300]


def apply_ia_hocr(ex, pdf_path):
    """Use the Internet Archive's OCR (<stem>_hocr_searchtext.txt.gz + <stem>_hocr_pageindex.json.gz,
    downloaded next to the PDF) for pages without a text layer, instead of running Tesseract."""
    import gzip
    stem = pdf_path[:-4]
    text_f, index_f = stem + "_hocr_searchtext.txt.gz", stem + "_hocr_pageindex.json.gz"
    if not (os.path.exists(text_f) and os.path.exists(index_f)):
        return
    try:
        with gzip.open(text_f, "rb") as f:
            text = f.read().decode("utf-8", "replace")
        with gzip.open(index_f, "rb") as f:
            index = json.loads(f.read())
    except (OSError, ValueError, EOFError):
        return
    covered = set()
    for i, entry in enumerate(index):
        if i >= len(ex.pages):
            break
        page = ex.pages[i]
        if len(page["text"]) < C.extract["ocr_min_chars"]:
            ocr = text[entry[0]:entry[1]].strip()
            if ocr:
                page["text"] = ocr if len(page["text"]) < 50 else page["text"] + "\n\n" + ocr
                page["ocr"] = True
            covered.add(page["n"])
    ex.jobs = [(n, ref) for n, ref in ex.jobs if n not in covered]


def stage_a_container(spec):
    """Archives streamed member by member, mailboxes, record files -> one JSONL shard."""
    rel, ctype = spec["relpath"], spec["ctype"]
    out = spec["id"] + ".jsonl"
    path = os.path.join(C.extracted_dir, out)
    jobs, n_docs, note = [], 0, ""
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        def emit(doc):
            nonlocal n_docs
            fh.write(json.dumps(doc, ensure_ascii=False) + "\n")
            n_docs += 1
        full = os.path.join(C.root, rel)
        if ctype in STREAMED:
            members_on = set(C.extract["archive_members"])
            min_img = C.extract["min_image_kb"] * 1000

            def wanted(name):
                f = formats.format_of(name)
                return f is not None and f in members_on and f != "mbox"
            skipped = 0
            try:
                for name, data, why in archives.stream_members(full, ctype, wanted, C.extract["max_member_mb"] * 1_000_000):
                    if data is None:
                        skipped += 1
                        continue
                    fmt = formats.format_of(name)
                    if fmt == "image" and len(data) < min_img:
                        continue
                    mrel = f"{rel}!/{name}"
                    doc = {"id": doc_id_for(mrel), "relpath": mrel, "kind": fmt, "member": name, "sources": [rel],
                           "src": {"archive": rel, "atype": ctype, "member": name}, "stat": spec["stat"],
                           "sha1": hashlib.sha1(data).hexdigest()}
                    try:
                        jobs += extract_one(fmt, data, name, None, doc)
                    except Exception as e:
                        doc["error"], doc["pages"] = repr(e)[:500], []
                    emit(doc)
            except Exception as e:
                note = f"archive stream stopped: {e!r}"[:300]
            note = note or (f"{skipped} members skipped" if skipped else "")
        elif ctype == "mbox":
            box = mailbox.mbox(full, create=False)
            try:
                for i, key in enumerate(box.iterkeys(), 1):
                    data = box.get_bytes(key)
                    mrel = f"{rel}#{i}"
                    doc = {"id": doc_id_for(mrel), "relpath": mrel, "kind": "email", "sources": [rel],
                           "src": {"mbox": rel, "index": i}, "stat": spec["stat"], "sha1": hashlib.sha1(data).hexdigest()}
                    try:
                        jobs += extract_one("email", data, f"message-{i}.eml", None, doc,
                                            staged_src=None)
                    except Exception as e:
                        doc["error"], doc["pages"] = repr(e)[:500], []
                    emit(doc)
            finally:
                box.close()
        else:
            rec = C.records[spec["rec"]]
            adapter = records.ADAPTERS.get(ctype)
            if adapter is None:
                raise ValueError(f"unknown record adapter {ctype!r} (known: {', '.join(records.ADAPTERS)})")
            for doc in adapter(C.root, rel, rec, C):
                doc["stat"] = spec["stat"]
                emit(doc)
    os.replace(path + ".tmp", path)
    return rel, [out], jobs, (note + f" ({n_docs} documents)").strip()


def _write_json(path, doc):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    os.replace(tmp, path)


# =========================================================================== OCR

def ocr_cache_path(doc_id, n):
    return os.path.join(C.ocr_dir, doc_id, f"{n:04d}.txt")


def stage_b(job):
    doc_id, n, ref = job
    cache = ocr_cache_path(doc_id, n)
    if os.path.exists(cache):
        return doc_id, n, None
    try:
        import pymupdf
        if "pdf" in ref:
            src = ref["pdf"]
            if "file" in src:
                pdf = pymupdf.open(os.path.join(C.root, src["file"]))
            else:
                pdf = pymupdf.open(stream=read_src(src), filetype="pdf")
            img = formats.render_page_png(pdf[ref["page"] - 1])
        else:
            src = ref["image"]
            name = src.get("file") or src.get("member") or src.get("staged") or ""
            img = formats.image_for_ocr(read_src(src), name)
        text = ocr_image_bytes(img, lang=C.extract["ocr_lang"])
    except Exception as e:
        return doc_id, n, repr(e)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    tmp = cache + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, cache)
    return doc_id, n, None


def merge_ocr(page, ocr):
    layer = page["text"]
    if len(layer) < 50:
        page["text"], page["ocr"] = ocr or layer, bool(ocr)
    elif len(ocr) > len(layer) * 1.3:
        # slide with a little real text plus text baked into images: keep both
        page["text"], page["ocr"] = layer + "\n\n" + ocr, True


def read_ocr_cache(job):
    """Cached OCR text for a page, or None. A cache file that is not valid UTF-8 (seen on exFAT drives
    under heavy write load) is deleted and the page OCR'd again."""
    cache = ocr_cache_path(job[0], job[1])
    if not os.path.exists(cache):
        return None
    try:
        with open(cache, encoding="utf-8") as f:
            return f.read().strip()
    except UnicodeDecodeError:
        print(f"[ocr] corrupt cache file {cache}; running OCR on the page again", flush=True)
        os.remove(cache)
    _, _, err = stage_b(job)
    if err:
        print(f"[ocr] {job[0]} page {job[1]}: {err}", flush=True)
        return None
    with open(cache, encoding="utf-8") as f:
        return f.read().strip()


def stage_c(out_file, jobs_for_file):
    """Merge cached OCR text into the extracted file. Returns True if every OCR job had a result."""
    path = os.path.join(C.extracted_dir, out_file)
    wanted = collections.defaultdict(list)
    for job in jobs_for_file:
        wanted[job[0]].append(job)
    complete = True

    def merge(doc):
        nonlocal complete
        for job in wanted.get(doc["id"], ()):
            ocr = read_ocr_cache(job)
            if ocr is None:
                complete = False
                continue
            n = job[1]
            if 0 < n <= len(doc["pages"]):
                merge_ocr(doc["pages"][n - 1], ocr)
        return doc

    if out_file.endswith(".jsonl"):
        tmp = path + ".tmp"
        with open(path, encoding="utf-8") as src, open(tmp, "w", encoding="utf-8") as dst:
            for line in src:
                dst.write(json.dumps(merge(json.loads(line)), ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    else:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        _write_json(path, merge(doc))
    return complete


# =========================================================================== main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True, help="corpus id (corpora/<id>.toml) or path to a .toml file")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    ap.add_argument("--limit", type=int, default=0, help="only the first N sources (trial runs)")
    ap.add_argument("--only", default="", help="only sources whose path matches this glob")
    ap.add_argument("--force", action="store_true", help="re-extract unchanged sources too")
    ap.add_argument("--no-ocr", action="store_true")
    args = ap.parse_args()
    global C
    C = load_corpus(args.corpus)
    if args.no_ocr:
        C.extract["ocr"] = False
    if not C.root or not os.path.isdir(C.root):
        raise SystemExit(f"[{C.id}] root folder not found: {C.root!r} (set `root` in {C.path})")
    for d in (C.extracted_dir, C.ocr_dir):
        os.makedirs(d, exist_ok=True)
    print(f"[{C.id}] {C.root}\n[{C.id}] packs: {', '.join(C.packs)}; data: {C.data_dir}", flush=True)

    t0 = time.time()
    specs, skipped = discover(C)
    if args.only:
        specs = [s for s in specs if fnmatch.fnmatch(s["relpath"], args.only)]
    partial = bool(args.only or args.limit)
    if args.limit:
        specs = specs[:args.limit]
    kinds = collections.Counter(s.get("ctype") or s["kind"] for s in specs)
    print(f"[discover] {len(specs)} sources in {time.time()-t0:.1f}s: "
          + ", ".join(f"{k} {n}" for k, n in kinds.most_common()), flush=True)
    if skipped:
        print("[discover] not indexed: " + ", ".join(f"{k} ×{n}" for k, n in skipped.most_common(15)), flush=True)

    manifest_path = os.path.join(C.data_dir, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    todo = []
    for s in specs:
        m = manifest.get(s["relpath"])
        if (not args.force and m and m.get("stat") == s["stat"] and m.get("complete")
                and all(os.path.exists(os.path.join(C.extracted_dir, o)) for o in m["out"])):
            continue
        todo.append(s)
    print(f"[extract] {len(specs)-len(todo)} unchanged, {len(todo)} to extract with {args.workers} workers", flush=True)

    jobs, outs, notes = [], {}, []
    t1 = time.time()
    with ProcessPoolExecutor(args.workers, initializer=_init, initargs=(C.path,)) as ex:
        futs = {ex.submit(stage_a, s): s for s in todo}
        for k, fut in enumerate(as_completed(futs), 1):
            s = futs[fut]
            rel, out, j, note = fut.result()
            outs[rel] = (s, out, j)
            jobs += j
            if note:
                notes.append(f"{rel}: {note}")
            if k % 200 == 0 or k == len(futs):
                print(f"[extract] {k}/{len(futs)}  {time.time()-t1:.0f}s", flush=True)
    for n in notes[:40]:
        print("   ", n)
    if len(notes) > 40:
        print(f"    ... {len(notes)-40} more")

    _init(C.path)
    todo_ocr = [j for j in jobs if not os.path.exists(ocr_cache_path(j[0], j[1]))]
    print(f"[ocr] {len(jobs)} pages need OCR: {len(jobs)-len(todo_ocr)} cached, {len(todo_ocr)} to run", flush=True)
    t2, errors = time.time(), 0
    if todo_ocr:
        with ProcessPoolExecutor(args.workers, initializer=_init, initargs=(C.path,)) as ex:
            futs = [ex.submit(stage_b, j) for j in todo_ocr]
            for k, fut in enumerate(as_completed(futs), 1):
                _, _, err = fut.result()
                errors += bool(err)
                if k % 100 == 0 or k == len(futs):
                    rate = k / max(time.time() - t2, 1e-6)
                    eta = (len(futs) - k) / max(rate, 1e-6)
                    print(f"[ocr] {k}/{len(futs)}  {rate:.1f} pages/s  eta {eta/60:.1f} min  errors={errors}", flush=True)

    # merge OCR into the extracted files and record what is complete
    for rel, (s, out, j) in outs.items():
        complete = bool(out)
        by_file = collections.defaultdict(list)
        for job in j:
            by_file[out[0] if len(out) == 1 else job[0] + ".json"].append(job)
        for f, lst in by_file.items():
            complete = stage_c(f, lst) and complete
        manifest[rel] = {"stat": s["stat"], "out": out, "complete": complete}
    if not partial:
        live = {s["relpath"] for s in specs}
        for rel in [r for r in manifest if r not in live]:
            for o in manifest.pop(rel)["out"]:
                try:
                    os.remove(os.path.join(C.extracted_dir, o))
                except OSError:
                    pass
        # legacy outputs written before the manifest existed
        known = {o for m in manifest.values() for o in m["out"]}
        for fn in os.listdir(C.extracted_dir):
            if fn.endswith((".json", ".jsonl")) and fn not in known:
                os.remove(os.path.join(C.extracted_dir, fn))
    tmp = manifest_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    os.replace(tmp, manifest_path)
    n_out = sum(len(m["out"]) for m in manifest.values())
    print(f"[done] {n_out} extracted files in {(time.time()-t0)/60:.1f} min"
          + (" (partial run: --limit/--only)" if partial else ""), flush=True)


if __name__ == "__main__":
    main()
