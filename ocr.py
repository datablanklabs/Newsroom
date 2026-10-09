"""OCR helper: renders images to Tesseract via stdin/stdout (no temp files)."""
import os
import shutil
import subprocess

TESSERACT = os.environ.get("TESSERACT") or shutil.which("tesseract") or "/opt/homebrew/bin/tesseract"


def ocr_image_bytes(data: bytes, timeout: int = 180, lang: str = "eng") -> str:
    """OCR encoded image bytes (PNG/JPEG/TIFF) and return plain text. lang: Tesseract languages, e.g. "eng+rus"."""
    # --psm 3: automatic page segmentation (good default for slides and memos).
    # OMP_THREAD_LIMIT=1 because we parallelise across processes instead.
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    try:
        out = subprocess.run(
            [TESSERACT, "stdin", "stdout", "-l", lang, "--psm", "3"],
            input=data, capture_output=True, timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired:
        return ""
    return out.stdout.decode("utf-8", "replace")
