"""Utilities to extract text from CV files."""

from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from pypdf import PdfReader


def parse_cv_file(filename: str, file_bytes: bytes) -> str:
    """Extract normalized text from supported CV file formats."""

    extension = Path(filename).suffix.lower()

    if extension == ".pdf":
        return _parse_pdf(file_bytes)

    if extension == ".docx":
        return _parse_docx(file_bytes)

    if extension == ".txt":
        return file_bytes.decode("utf-8", errors="ignore").strip()

    raise ValueError("unsupported file type; use .pdf, .docx, or .txt")


def _parse_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    if not text:
        raise ValueError("could not extract text from pdf")
    return text


def _parse_docx(file_bytes: bytes) -> str:
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
    return parsed_text
