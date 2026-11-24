"""Validate an uploaded resume and extract its text. Never executes document content."""
import io
import re
import zipfile
from pathlib import Path

from app.utils.responses import ApiError

ALLOWED = {".pdf": "application/pdf",
           ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
MAX_PAGES = 15
MAX_TEXT = 30000
MIN_TEXT = 100
MAX_ZIP_UNCOMPRESSED = 30 * 1024 * 1024
MAX_ZIP_ENTRIES = 1000


def _bad(code, msg, status=400):
    return ApiError(code, msg, status)


def _pdf_text(data: bytes) -> str:
    import fitz  # PyMuPDF
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:
        raise _bad("unreadable_file", "This PDF could not be opened. It may be damaged.")
    try:
        if doc.needs_pass or doc.is_encrypted:
            raise _bad("encrypted_file", "Password-protected PDFs are not supported. Upload an unlocked copy.")
        if doc.page_count > MAX_PAGES:
            raise _bad("too_many_pages", f"Resumes can have at most {MAX_PAGES} pages.")
        return "\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()


def _docx_text(data: bytes) -> str:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise _bad("invalid_file_content", "This file is not a valid DOCX document.")
    infos = zf.infolist()
    if len(infos) > MAX_ZIP_ENTRIES or sum(i.file_size for i in infos) > MAX_ZIP_UNCOMPRESSED:
        raise _bad("invalid_file_content", "This document is too large or complex to process.")
    names = {i.filename for i in infos}
    if "word/document.xml" not in names or "[Content_Types].xml" not in names:
        raise _bad("invalid_file_content", "This file is not a valid DOCX document.")
    if any(n.lower().endswith(".bin") and "vba" in n.lower() for n in names):
        raise _bad("macro_content", "Documents containing macros are not accepted.")
    import docx
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception:
        raise _bad("unreadable_file", "This DOCX could not be read. It may be damaged.")
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            seen = set()
            for cell in row.cells:
                if id(cell._tc) not in seen:
                    seen.add(id(cell._tc))
                    parts.append(cell.text)
    return "\n".join(parts)


def normalize_text(text: str) -> str:
    text = text.replace("\r", "\n").replace("\xa0", " ").replace("\t", " ").replace("\u200b", "")
    lines = []
    for raw in text.split("\n"):
        line = re.sub(r"[ ]{2,}", " ", raw).strip()
        line = re.sub(r"^[•▪●◦■□►▸·*]\s*", "- ", line)
        lines.append(line)
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return out


def validate_and_extract(data: bytes, filename: str) -> tuple[str, str]:
    """Returns (extension, text). Raises ApiError with a user-facing message."""
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise _bad("invalid_file_type", "Upload a PDF or DOCX file.", 415)
    if not data:
        raise _bad("empty_file", "This file is empty.")
    if ext == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise _bad("invalid_file_content", "This file is not a real PDF, even though its name ends in .pdf.")
        text = _pdf_text(data)
    else:
        if not data.startswith(b"PK"):
            raise _bad("invalid_file_content", "This file is not a real DOCX, even though its name ends in .docx.")
        text = _docx_text(data)
    text = normalize_text(text)
    if len(text) < MIN_TEXT:
        raise _bad("no_text", "We couldn't find readable text in this file. Scanned images aren't supported yet; "
                              "upload a text-based PDF or DOCX.")
    return ext, text[:MAX_TEXT]
