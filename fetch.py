"""
Download a corpus's source files from the web into its `root` folder, as declared in the
[fetch] section of corpora/<id>.toml. Resumable, rate-limited and polite.

  .venv/bin/python build/fetch.py --corpus jfk-2025              # download (resumes where it stopped)
  .venv/bin/python build/fetch.py --corpus jfk-2025 --dry-run    # list what would be fetched
  .venv/bin/python build/fetch.py --corpus jfk-2025 --status     # progress so far
  .venv/bin/python build/fetch.py --corpus jfk-2025 --limit 50   # trial run

Fetch types:
  links      scrape listing pages for file links (NARA release pages, DOJ Epstein data sets);
             "{page}" in a page URL is paginated from 0 until a page adds nothing new
  ia         Internet Archive items matching a search query (e.g. the ciareadingroom mirror of CREST)
  wayback    captures of a site in the Wayback Machine (CDX API), for sites that block scripts
  wordpress  every post of a WordPress site (REST API), downloading the files its posts link to

Files land under root/<path taken from the URL>; partial downloads are written as *.part and
renamed when complete, so an interrupted run never leaves a truncated file behind. State lives in
data/<corpus>/fetch/: urls.jsonl (the discovered file list; delete it or pass --relist to rediscover)
and done.jsonl (completed downloads).
"""
import argparse
import concurrent.futures as cf
import hashlib
import html
import json
import mimetypes
import os
import re
import signal
import sys
import threading
import time
import urllib.parse

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from lib.config import load_corpus  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
      "Version/17.0 Safari/605.1.15 newsroom-archiver/1.0 (personal research archive)")
STOP = threading.Event()
LOG = {"file": None}


def log(*a):
    line = " ".join(str(x) for x in (time.strftime("%Y-%m-%d %H:%M:%S"),) + a)
    print(line, flush=True)
    if LOG["file"]:
        LOG["file"].write(line + "\n")
        LOG["file"].flush()


class Http:
    """One session per run; a minimum interval between requests to each host; retries with backoff."""

    def __init__(self, interval, retries=6):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8"})
        adapter = requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16)
        self.s.mount("https://", adapter)
        self.s.mount("http://", adapter)
        self.interval, self.retries = interval, retries
        self.lock, self.next_at = threading.Lock(), {}

    def _wait(self, url):
        host = urllib.parse.urlsplit(url).netloc
        with self.lock:
            now = time.monotonic()
            at = max(now, self.next_at.get(host, 0))
            self.next_at[host] = at + self.interval
        if at > now:
            time.sleep(at - now)

    def _cooldown(self, url, seconds):
        host = urllib.parse.urlsplit(url).netloc
        with self.lock:
            self.next_at[host] = max(self.next_at.get(host, 0), time.monotonic() + seconds)

    def get(self, url, stream=False, ok404=False, headers=None):
        delay = 5
        for attempt in range(self.retries):
            if STOP.is_set():
                raise KeyboardInterrupt
            self._wait(url)
            try:
                r = self.s.get(url, stream=stream, timeout=(30, 120), allow_redirects=True, headers=headers)
            except requests.RequestException as e:
                err = repr(e)
            else:
                if r.status_code in (200, 206):
                    return r
                if r.status_code in (404, 410) and ok404:
                    return None
                if r.status_code not in (429, 500, 502, 503, 504, 520, 522, 524):
                    raise RuntimeError(f"HTTP {r.status_code} for {url}")
                err = f"HTTP {r.status_code}"
                retry_after = r.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    delay = max(delay, int(retry_after))
                if r.status_code in (429, 503):     # throttled: pause every request to this host, not just this one
                    self._cooldown(url, delay)
            log(f"   retry {attempt + 1}/{self.retries} in {delay}s: {err} {url[:120]}")
            time.sleep(delay)
            delay = min(delay * 2, 600)
        raise RuntimeError(f"gave up on {url}")


# =========================================================================== listing sources

def _abs(base, href):
    return urllib.parse.urljoin(base, html.unescape(href))


def list_links(F, http):
    """Scrape listing pages for links to files with the wanted extensions."""
    exts = tuple(e.lower() for e in F.get("extensions", [".pdf"]))
    pattern = re.compile(F["link_pattern"]) if F.get("link_pattern") else None
    pages = []
    for p in F["pages"]:
        if "{n}" in p:
            lo, hi = F.get("n_range", [1, 1])
            pages += [p.replace("{n}", str(n)) for n in range(lo, hi + 1)]
        else:
            pages.append(p)
    seen = set()
    for page in pages:
        n_page = 0
        while True:
            url = page.replace("{page}", str(n_page))
            r = http.get(url, ok404=True)
            new = 0
            if r is not None:
                for href in re.findall(r'href="([^"]+)"', r.text):
                    u = _abs(url, href)
                    path = urllib.parse.urlsplit(u).path.lower()
                    if not path.endswith(exts) or (pattern and not pattern.search(u)) or u in seen:
                        continue
                    seen.add(u)
                    new += 1
                    yield {"url": u, "path": _dest_path(u, F)}
            if "{page}" not in page or r is None or new == 0:
                break
            n_page += 1
            if n_page % 50 == 0:
                log(f"   listing {page.split('?')[0]}: {n_page} pages, {len(seen)} files so far")


def list_ia(F, http):
    """Internet Archive items via the scrape API; one file per item (pattern from the identifier)."""
    cursor, n = None, 0
    suffixes = F.get("files", [".pdf"])
    strip = F.get("strip_identifier_prefix", "")
    while True:
        params = {"q": F["query"], "fields": "identifier", "count": 10000}
        if cursor:
            params["cursor"] = cursor
        r = http.get("https://archive.org/services/search/v1/scrape?" + urllib.parse.urlencode(params))
        data = r.json()
        for item in data.get("items", []):
            ident = item["identifier"]
            stem = ident[len(strip):] if strip and ident.startswith(strip) else ident
            for suf in suffixes:
                name = stem + suf
                yield {"url": f"https://archive.org/download/{ident}/{urllib.parse.quote(name)}", "path": _shard(stem, F) + name,
                       "ia": ident}
            n += 1
        cursor = data.get("cursor")
        log(f"   listed {n} Internet Archive items")
        if not cursor:
            break


def list_ia_item(F, http):
    """Selected original files of one Internet Archive item, with IA's MD5 (and optional SHA-256) to verify."""
    meta = http.get(f"https://archive.org/metadata/{F['item']}").json()
    rx = re.compile(F.get("files_regex", ".*"))
    sha = F.get("sha256", {})
    for f in meta.get("files", []):
        if f.get("source") != "original" or not rx.search(f["name"]):
            continue
        yield {"url": f"https://archive.org/download/{F['item']}/{urllib.parse.quote(f['name'])}",
               "path": F.get("dest_prefix", "") + f["name"], "size": int(f.get("size") or 0),
               "md5": f.get("md5", ""), "sha256": sha.get(f["name"], "")}


def _shard(stem, F):
    """Folder for an item: e.g. CREST 'cia-rdp88-01350r000200300069-6' -> 'cia-rdp88-01350r/'."""
    rx = F.get("shard_pattern")
    if not rx:
        return ""
    m = re.match(rx, stem)
    return (m.group(1) if m else "other") + "/"


def list_wayback(F, http):
    """Captured files of a site in the Wayback Machine, in CDX batches chained by resume key. (The paged
    API's index lags months behind and answers '- -' for recent captures; collapse=urlkey times out.)
    One capture per destination path: '…/part-01' and '…/part-01/at_download/file' are the same file."""
    params = {"url": F["url"], "filter": ["statuscode:200"] + ([f"mimetype:{F['mimetype']}"] if F.get("mimetype") else []),
              "fl": "timestamp,original", "limit": int(F.get("cdx_limit", 2000)), "showResumeKey": "true"}
    base = "https://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode(params, doseq=True)
    ext = mimetypes.guess_extension(F.get("mimetype", "")) or ""
    seen, key, batches = set(), "", 0
    while True:
        text = _cdx(http, base + (f"&resumeKey={urllib.parse.quote(key)}" if key else ""))
        rows, _, key = text.partition("\n\n")
        key = key.strip()
        for line in rows.splitlines():
            parts = line.split(" ", 1)
            if len(parts) != 2:
                continue
            ts, original = parts
            if F.get("link_pattern") and not re.search(F["link_pattern"], original):
                continue
            path = "/".join(p.strip() for p in _dest_path(original, F).split("/") if p.strip())
            if ext and not path.lower().endswith(ext):
                path += ext
            if path.lower() in seen:
                continue
            seen.add(path.lower())
            yield {"url": f"https://web.archive.org/web/{ts}id_/{original}", "path": path}
        batches += 1
        if batches % 10 == 0 or not key:
            log(f"   CDX: {batches} batches, {len(seen)} files")
        if not key:
            break


def _cdx(http, url, wait=300, max_hours=72):
    """The CDX API answers 200 with an HTML 'Temporarily Offline' page (or '- -') during outages:
    wait and retry rather than mistaking that for an empty result."""
    deadline = time.time() + max_hours * 3600
    while True:
        try:
            r = http.get(url, ok404=True)
            text = r.text if r is not None else ""
        except RuntimeError:              # 5xx / 429 after all retries: treat like an outage
            text = "<"
        if not text.lstrip().startswith(("<", "- -")):
            return text
        if time.time() > deadline:
            raise RuntimeError("Wayback CDX API still offline; run again later")
        log(f"   Wayback CDX API offline; retrying in {wait // 60} min")
        for _ in range(wait):
            if STOP.is_set():
                raise KeyboardInterrupt
            time.sleep(1)


def list_wordpress(F, http):
    """All posts via /wp-json/wp/v2/posts; downloads the files their content links to."""
    pattern = re.compile(F.get("link_pattern", r"\.(pdf|zip)$"), re.I)
    page, seen = 1, set()
    while True:
        url = F["api"].rstrip("/") + f"/wp/v2/posts?per_page=100&page={page}&_fields=id,link,content"
        r = http.get(url, ok404=True)
        if r is None:
            break
        posts = r.json()
        if not posts:
            break
        for p in posts:
            for href in re.findall(r'href="([^"]+)"', p.get("content", {}).get("rendered", "")):
                u = _clean_href(p["link"], href)
                if pattern.search(u) and u not in seen:
                    seen.add(u)
                    yield {"url": u, "path": _dest_path(u, F), "post": p["link"]}
        log(f"   listed {page * 100} posts, {len(seen)} files")
        if page >= int(r.headers.get("X-WP-TotalPages", page)):
            break
        page += 1


def _clean_href(base, href):
    """Repair hand-made links: a URL pasted twice ('…/nro/https://host/…') or a host without a scheme."""
    href = html.unescape(href).strip()
    starts = [m.start() for m in re.finditer(r"https?://", href)]
    if len(starts) > 1:
        href = href[starts[-1]:]
    if re.match(r"(?:www\.|documents\d*\.)[\w.-]+\.\w+/", href):
        href = "https://" + href
    return urllib.parse.urljoin(base, href)


def _dest_path(url, F):
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    for pre in F.get("strip_prefix", []) if isinstance(F.get("strip_prefix"), list) else [F.get("strip_prefix", "")]:
        if pre and path.startswith(pre):
            path = path[len(pre):]
            break
    path = re.sub(r"/at_download/file$", ".pdf", path)          # Plone (FBI Vault) download URLs
    path = path.lstrip("/")
    parts = [re.sub(r'[<>:"\\|?*\x00-\x1f]', "_", p)[:180] for p in path.split("/") if p not in ("", ".", "..")]
    return "/".join(parts) or "index"


LISTERS = {"links": list_links, "ia": list_ia, "ia-item": list_ia_item, "wayback": list_wayback, "wordpress": list_wordpress}


# =========================================================================== download

def _hash_file(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


class Incomplete(RuntimeError):
    pass


def download(item, root, http, max_bytes, resumes=1000):
    """Fetch one file to root/<path>. Interrupted transfers resume from the .part file (HTTP Range), both
    across runs and within one: a connection that drops mid-file (common on 100+ GB archive.org files, and
    on the Wayback Machine, which can cut every connection after a few hundred KB) is picked up again after
    a short pause as long as each attempt makes progress. Files with a known MD5 / SHA-256 are verified
    before they are renamed into place."""
    tmp = os.path.join(root, item["path"]) + ".part"
    run = {}                                       # shared with _download_once across attempts
    for attempt in range(resumes + 1):
        try:
            return _download_once(item, root, http, max_bytes, run)
        except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError, Incomplete) as e:
            if attempt == resumes or not run.get("progress"):
                raise
            size = os.path.getsize(tmp) if os.path.exists(tmp) else 0
            log(f"   connection dropped at {size/1e6:.1f} MB ({e.__class__.__name__}); resuming in 5s {item['path'][:80]}")
            if STOP.wait(5):
                raise KeyboardInterrupt


def _download_once(item, root, http, max_bytes, run=None):
    """One attempt. run carries state across attempts: "start", the bytes kept from earlier runs (the byte
    count returned is what this run added to the file), and "progress", whether this attempt received data."""
    run = {} if run is None else run
    dest = os.path.join(root, item["path"])
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return item, "exists", os.path.getsize(dest)
    if max_bytes and item.get("size", 0) > max_bytes:
        return item, f"skipped ({item['size']/1e9:.1f} GB > limit)", 0
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    have = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    run.setdefault("start", have)
    run["progress"] = False
    r = http.get(item["url"], stream=True, ok404=True, headers={"Range": f"bytes={have}-"} if have else None)
    if r is None:
        return item, "missing", 0
    if r.status_code == 200:
        have = run["start"] = 0                    # server ignored the range: start over
    if "text/html" in r.headers.get("Content-Type", "") and not item["path"].lower().endswith((".html", ".htm")):
        r.close()
        raise RuntimeError(f"got a web page instead of a file (login, age or bot check?) for {item['url'][:120]}")
    clen = r.headers.get("Content-Length")
    size = int(clen) + have if clen else 0          # 0: unknown (chunked); a resume adds to what we have
    if max_bytes and size > max_bytes:
        r.close()
        return item, f"skipped ({size/1e9:.1f} GB > limit)", 0
    got = have
    with open(tmp, "ab" if have else "wb") as f:
        for chunk in r.iter_content(1 << 16):      # small reads: a connection cut short still leaves its data
            if STOP.is_set():
                r.close()
                raise KeyboardInterrupt
            f.write(chunk)
            got += len(chunk)
            run["progress"] = True
    expected = item.get("size") or size
    if r.headers.get("Content-Encoding") in (None, "", "identity") and expected and got != expected:
        raise Incomplete(f"incomplete: {got}/{expected} bytes for {item['url'][:120]} (rerun to resume)")
    for algo in ("md5", "sha256"):
        want = (item.get(algo) or "").lower()
        if want:
            have_hash = _hash_file(tmp, algo)
            if have_hash != want:
                os.replace(tmp, tmp + f".bad-{algo}")
                raise RuntimeError(f"{algo} mismatch for {item['path']}: {have_hash} != {want}")
    os.replace(tmp, dest)
    return item, "ok", got - run["start"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True, action="append",
                    help="corpus id; repeat to fetch several one after another (e.g. sources on the same host)")
    ap.add_argument("--log", action="store_true", help="also append progress to data/<corpus>/fetch.log")
    ap.add_argument("--dry-run", action="store_true", help="discover and count files, download nothing")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--relist", action="store_true", help="rediscover the file list instead of reusing urls.jsonl")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    for cid in args.corpus:
        if STOP.is_set():
            break
        C = load_corpus(cid)
        if args.log:
            os.makedirs(C.data_dir, exist_ok=True)
            LOG["file"] = open(os.path.join(C.data_dir, "fetch.log"), "a", encoding="utf-8")
        try:
            fetch_corpus(C, args)
        except Exception as e:
            log(f"[{C.id}] failed: {e!r}"[:500])
        finally:
            if LOG["file"]:
                LOG["file"].close()
                LOG["file"] = None


def fetch_corpus(C, args):
    F = C.raw.get("fetch")
    if not F:
        raise SystemExit(f"{C.path} has no [fetch] section")
    state = os.path.join(C.data_dir, "fetch")
    os.makedirs(state, exist_ok=True)
    urls_path, done_path = os.path.join(state, "urls.jsonl"), os.path.join(state, "done.jsonl")
    done = {}
    if os.path.exists(done_path):
        with open(done_path, encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                done[d["url"]] = d
    if args.status:
        listed = sum(1 for _ in open(urls_path)) if os.path.exists(urls_path) else 0
        size = sum(d.get("bytes", 0) for d in done.values())
        print(f"[{C.id}] {len(done)} of {listed or '?'} files done, {size/1e9:.1f} GB in {C.root}")
        return
    http = Http(F.get("interval", 1.0), int(F.get("retries", 6)))
    os.makedirs(C.root, exist_ok=True)
    log(f"[{C.id}] fetch type={F['type']} -> {C.root}")

    saved = os.path.exists(urls_path) and not args.relist and os.path.getsize(urls_path) > 0
    listing = {"complete": False, "n": 0}

    def items():
        """Saved list, or discover while downloading (the list is saved once discovery completes)."""
        if saved:
            with open(urls_path, encoding="utf-8") as f:
                for line in f:
                    listing["n"] += 1
                    yield json.loads(line)
            listing["complete"] = True
            return
        tmp = urls_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as out:
            for it in LISTERS[F["type"]](F, http):
                out.write(json.dumps(it) + "\n")
                out.flush()
                listing["n"] += 1
                yield it
                if STOP.is_set():
                    return
        listing["complete"] = True
        os.replace(tmp, urls_path)

    log(f"[{C.id}] {'using the saved file list' if saved else 'discovering files while downloading'}"
        f"; {len(done)} already done")
    max_bytes = int(F.get("max_file_gb", 25) * 1e9)
    workers = F.get("concurrency", 2)
    n_ok = n_bytes = n_err = n_new = 0
    t0, last_report = time.time(), 0
    shown = 0

    def handle(fut, it, dlog):
        nonlocal n_ok, n_bytes, n_err
        try:
            _, status, got = fut.result()
        except KeyboardInterrupt:
            return
        except Exception as e:
            n_err += 1
            log(f"   error: {e}"[:300])
            return
        if status in ("ok", "exists", "missing") or status.startswith("skipped"):
            dlog.write(json.dumps({"url": it["url"], "path": it["path"], "status": status, "bytes": got}) + "\n")
            dlog.flush()
            if status.startswith("skipped") or status == "missing":
                log(f"   {status}: {it['url'][:150]}")
        n_ok += status in ("ok", "exists")
        n_bytes += got

    with open(done_path, "a", encoding="utf-8") as dlog, cf.ThreadPoolExecutor(workers) as ex:
        pending = {}
        try:
            for it in items():
                if it["url"] in done:
                    continue
                n_new += 1
                if args.dry_run:
                    if shown < 10:
                        print("   ", it["path"], "<-", it["url"])
                        shown += 1
                    if args.limit and n_new >= args.limit:
                        break
                    continue
                while len(pending) >= workers * 4:
                    finished, _ = cf.wait(pending, return_when=cf.FIRST_COMPLETED)
                    for fut in finished:
                        handle(fut, pending.pop(fut), dlog)
                pending[ex.submit(download, it, C.root, http, max_bytes)] = it
                if time.time() - last_report > 60:
                    last_report = time.time()
                    rate = n_bytes / max(time.time() - t0, 1)
                    log(f"[{C.id}] listed {listing['n']}, downloaded {n_ok} ({n_bytes/1e9:.2f} GB, {rate/1e6:.1f} MB/s), errors {n_err}")
                if (args.limit and n_new >= args.limit) or STOP.is_set():
                    break
            for fut in cf.as_completed(list(pending)):
                handle(fut, pending.pop(fut), dlog)
        except KeyboardInterrupt:
            STOP.set()
        if STOP.is_set():
            log(f"[{C.id}] stopping; run again to resume")
            for f in pending:
                f.cancel()
    if args.dry_run:
        log(f"[{C.id}] dry run: {n_new} files to download" + ("" if listing["complete"] else " (listing stopped early)"))
        return
    log(f"[{C.id}] {'finished' if listing['complete'] and not STOP.is_set() else 'paused'}: {n_ok} files, "
        f"{n_bytes/1e9:.2f} GB this run, {n_err} errors (rerun to resume or retry)")


if __name__ == "__main__":
    main()
