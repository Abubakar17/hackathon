"""
Turns uploaded files into text for the extractor. Text PDFs, TXT and MD only: no OCR.
Several files become one document, each page under its own separator line, so a figure
stated differently in two files is seen as a conflict.
"""
import io
from typing import Any, Dict, List

MAX_FILES = 5
MAX_BYTES = 4 * 1024 * 1024
MAX_PAGES = 30
MAX_TEXT = 160_000


class UploadError(ValueError):
    pass


def read_pdf(data: bytes) -> List[str]:
    """Text of each page. Raises UploadError for anything that is not a readable text PDF."""
    if not data.startswith(b"%PDF-"):
        raise UploadError("this is not a PDF file")
    try:
        from pypdf import PdfReader
    except ImportError:
        raise UploadError("PDF reading needs the pypdf package (pip install -r requirements.txt)")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise UploadError("the PDF is password-protected")
        if len(reader.pages) > MAX_PAGES:
            raise UploadError(f"the PDF has more than {MAX_PAGES} pages")
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except UploadError:
        raise
    except Exception:
        raise UploadError("the PDF could not be read")
    if not any(pages):
        raise UploadError("the PDF has no text layer (a scan?); OCR is not supported")
    return pages


def read_upload(name: str, data: bytes) -> Dict[str, Any]:
    """One uploaded file -> {name, pages: [text], kind}."""
    if len(data) > MAX_BYTES:
        raise UploadError("the file is larger than 4 MB")
    lower = name.lower()
    if lower.endswith(".pdf"):
        pages, kind = read_pdf(data), "pdf"
    elif lower.endswith((".txt", ".md")):
        try:
            pages, kind = [data.decode("utf-8").strip()], "text"
        except UnicodeDecodeError:
            raise UploadError("the text file is not UTF-8")
        if not pages[0]:
            raise UploadError("the file is empty")
    else:
        raise UploadError("only PDF, TXT and MD files are supported")
    if sum(len(p) for p in pages) > MAX_TEXT:
        raise UploadError("the file holds too much text")
    return {"name": name, "kind": kind, "pages": pages}


def combine(files: List[Dict[str, Any]]) -> str:
    """One document for the extractor, every page under a separator naming its file and page."""
    parts = []
    for f in files:
        for i, text in enumerate(f["pages"], 1):
            if text:
                where = f"{f['name']} · page {i}" if f["kind"] == "pdf" else f["name"]
                parts.append(f"=== {where} ===\n{text}")
    return "\n\n".join(parts)
