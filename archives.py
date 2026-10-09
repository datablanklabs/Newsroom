"""
Read documents out of archives without unpacking them.

zip  random access with the standard library; each member is read into memory on demand.
tar  .tar/.tgz/.tar.gz/.tbz2/.tar.bz2/.txz/.tar.xz streamed with the standard library.
7z / rar  converted on the fly to a tar stream by libarchive's `bsdtar` (built into macOS), then
     streamed the same way. One pass per archive; nothing is written to disk.

Only members whose format is on the corpus allow-list are read, and only up to max_member_mb.
Member names are never used as file-system paths, so "../" tricks are harmless; executables,
scripts and anything else not on the allow-list are never read at all.
"""
import os
import shutil
import subprocess
import tarfile
import zipfile

BSDTAR = shutil.which("bsdtar")

TAR_SUFFIXES = (".tar", ".tgz", ".tar.gz", ".tbz", ".tbz2", ".tar.bz2", ".txz", ".tar.xz")


def archive_type(name):
    n = name.lower()
    if n.endswith(".zip"):
        return "zip"
    if n.endswith(TAR_SUFFIXES):
        return "tar"
    if n.endswith(".7z"):
        return "7z"
    if n.endswith(".rar"):
        return "rar"
    return None


def skip_member(name):
    base = os.path.basename(name.rstrip("/"))
    return (not base or base.startswith("._") or base == ".DS_Store" or "__MACOSX/" in name
            or name.endswith("/"))


def zip_members(path):
    """[(name, size, encrypted)] for regular members."""
    with zipfile.ZipFile(path) as z:
        return [(i.filename, i.file_size, bool(i.flag_bits & 0x1)) for i in z.infolist()
                if not i.is_dir() and not skip_member(i.filename)]


def read_zip_member(path, member, max_bytes=None):
    with zipfile.ZipFile(path) as z:
        info = z.getinfo(member)
        if max_bytes and info.file_size > max_bytes:
            raise ValueError(f"member is {info.file_size/1e6:.0f} MB (limit {max_bytes/1e6:.0f} MB)")
        return z.read(member)


def _open_stream(path, atype):
    if atype == "tar":
        return tarfile.open(path, mode="r|*"), None
    if not BSDTAR:
        raise RuntimeError(f"reading .{atype} archives needs bsdtar (libarchive)")
    proc = subprocess.Popen([BSDTAR, "-c", "-f", "-", "--format", "pax", "@" + path],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return tarfile.open(fileobj=proc.stdout, mode="r|"), proc


def stream_members(path, atype, wanted, max_bytes):
    """Yield (name, bytes | None, note) for every regular member; bytes only when wanted(name) is true
    and the member fits under max_bytes."""
    tf, proc = _open_stream(path, atype)
    try:
        for m in tf:
            if not m.isfile() or skip_member(m.name):
                continue
            if not wanted(m.name):
                yield m.name, None, "skipped"
                continue
            if max_bytes and m.size > max_bytes:
                yield m.name, None, f"too large ({m.size/1e6:.0f} MB)"
                continue
            f = tf.extractfile(m)
            yield m.name, (f.read() if f else b""), ""
    finally:
        tf.close()
        if proc:
            proc.kill()
            proc.wait()


def read_member(path, atype, member, max_bytes=None):
    """Random access to one member (slow for streamed formats: scans until found)."""
    if atype == "zip":
        return read_zip_member(path, member, max_bytes)
    for name, data, _ in stream_members(path, atype, lambda n: n == member, max_bytes):
        if name == member and data is not None:
            return data
    raise KeyError(member)
