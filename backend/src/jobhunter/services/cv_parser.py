"""Utilities to extract text from CV files."""

from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from pypdf import PdfReader


def parse_cv_file(filename: str, file_bytes: bytes) -> str:
    """Extract normalized text from supported CV file formats."""
    return parse_cv_file_pages(filename, file_bytes)[0]


def parse_cv_file_pages(filename: str, file_bytes: bytes) -> tuple[str, list[str]]:
    """Extract (joined_text, pages) from supported CV file formats.

    `pages` gives per-page text for PDFs (used for `ExtractionEvidence.source_page`); for
    formats with no real pagination (.docx, .txt) it is a single-element list holding the whole
    document, so evidence always resolves to page 1 there rather than being undefined.
    """
    extension = Path(filename).suffix.lower()

    if extension == ".pdf":
        return _parse_pdf(file_bytes)

    if extension == ".docx":
        return _parse_docx(file_bytes)

    if extension == ".txt":
        text = file_bytes.decode("utf-8", errors="ignore").strip()
        return text, [text]

    raise ValueError("unsupported file type; use .pdf, .docx, or .txt")


def _parse_pdf(file_bytes: bytes) -> tuple[str, list[str]]:
    reader = PdfReader(BytesIO(file_bytes))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    text = "\n".join(pages).strip()
    if not text:
        raise ValueError("could not extract text from pdf")
    return text, pages


def _parse_docx(file_bytes: bytes) -> tuple[str, list[str]]:
    with ZipFile(BytesIO(file_bytes)) as archive:
        document_xml = archive.read("word/document.xml")

    tree = ElementTree.fromstring(document_xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    lines = []

    for paragraph in tree.findall(".//w:p", namespace):
        texts = [node.text for node in paragraph.findall(".//w:t", namespace) if node.text]
        line = "".join(texts).strip()
        if line:
            lines.append(line)

    parsed_text = "\n".join(lines).strip()
    if not parsed_text:
        raise ValueError("could not extract text from docx")
    return parsed_text, [parsed_text]
