"""Read actual bytes, not adapter descriptions. No business oracle lives here."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def confined(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ":" in relative or "\\" in relative:
        raise ValueError("expected a portable relative path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError("path escapes run workspace")
    return path


def xlsx_cells(data: bytes) -> dict[tuple[str, str], str]:
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    result = {}
    with zipfile.ZipFile(io.BytesIO(data)) as book:
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            shared = ["".join(n.itertext()) for n in ET.fromstring(book.read("xl/sharedStrings.xml"))]
        rels = {r.attrib["Id"]: r.attrib["Target"] for r in ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))}
        for sheet in ET.fromstring(book.read("xl/workbook.xml")).findall("s:sheets/s:sheet", ns):
            target = rels[sheet.attrib[f"{{{rel_ns}}}id"]]
            name = target.lstrip("/") if target.startswith("/") else "xl/" + target
            for cell in ET.fromstring(book.read(name)).findall(".//s:c", ns):
                value = cell.find("s:v", ns)
                text = value.text or "" if value is not None else ""
                if cell.get("t") == "s":
                    text = shared[int(text)]
                elif cell.get("t") == "inlineStr":
                    text = "".join(cell.find("s:is", ns).itertext())
                result[sheet.attrib["name"], cell.attrib["r"]] = text
    return result


def pdf_pages(data: bytes) -> list[str]:
    from pypdf import PdfReader  # optional: a missing parser blocks the check, never silently passes
    return [page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages]


def text_content(data: bytes, suffix: str, depth: int = 0) -> str:
    if depth > 3 or len(data) > 20_000_000:
        raise ValueError("inspection resource limit")
    if suffix == ".zip":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if len(archive.infolist()) > 100 or sum(i.file_size for i in archive.infolist()) > 20_000_000:
                raise ValueError("archive inspection limit")
            return "\n".join(i.filename + "\n" + text_content(archive.read(i), Path(i.filename).suffix.lower(), depth + 1)
                             for i in archive.infolist() if not i.is_dir())
    if suffix == ".xlsx":
        return "\n".join(f"{sheet}!{cell}: {value}" for (sheet, cell), value in xlsx_cells(data).items())
    if suffix == ".pdf":
        return "\n".join(pdf_pages(data))
    if suffix in (".json", ".html", ".txt", ".eml", ".csv", ".md"):
        return data.decode("utf-8-sig")
    raise ValueError(f"unsupported content inspection: {suffix}")


def locate(data: bytes, locator: dict) -> str:
    kind = locator.get("type")
    if kind == "text":
        start, end = locator["start"], locator["end"]
        text = data.decode("utf-8-sig")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
            raise ValueError("invalid source character range")
        return text[start:end]
    if kind == "xlsx":
        return xlsx_cells(data)[locator["sheet"], locator["cell"]]
    if kind == "pdf":
        page = locator["page"]
        if type(page) is not int or page < 1:
            raise ValueError("invalid PDF page")
        quote = locator["quote"]
        if not quote or quote not in pdf_pages(data)[page - 1]:
            raise ValueError("quote absent from actual PDF page")
        return quote
    raise ValueError("unsupported locator")
