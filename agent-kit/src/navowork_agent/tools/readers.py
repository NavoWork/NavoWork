"""Bounded, read-only readers for common business document formats."""

from __future__ import annotations

import email
from email import policy
from io import BytesIO
from pathlib import Path
import re
from typing import Any
from zipfile import BadZipFile, ZipFile

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_RESULT_CHARACTERS = 100_000
MAX_RESULT_SECTIONS = 10_000
MAX_SECTION_CHARACTERS = 10_000
MAX_OOXML_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_OOXML_ENTRIES = 2_000
MAX_XLSX_SHEET_CELLS = 100_000
MAX_XLSX_NONEMPTY_CELLS = 100_000
MAX_XLSX_SCANNED_CELLS = 1_000_000
MAX_PDF_PAGES = 100
MAX_DOCX_ELEMENTS = 10_000

_MEDIA_EXTENSIONS = {
    ".txt": "text/plain",
    ".eml": "message/rfc822",
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _add_warning(warnings: list[str], message: str) -> None:
    if len(message) > 1_000:
        message = message[:1_000] + "…"
    if message not in warnings:
        if len(warnings) < 100:
            warnings.append(message)
        elif warnings[-1] != "Additional warnings omitted":
            warnings[-1] = "Additional warnings omitted"


def _bounded_field(value: Any, key: str, warnings: list[str], budget: list[int]) -> Any:
    if isinstance(value, str):
        limit = min(MAX_SECTION_CHARACTERS, budget[0])
        if len(value) > limit:
            value = value[:limit]
            _add_warning(warnings, f"Section {key} truncated at the result character limit")
        budget[0] -= len(value)
        return value
    if isinstance(value, dict):
        return {k: _bounded_field(v, key, warnings, budget) for k, v in value.items()}
    if isinstance(value, list):
        return [_bounded_field(v, key, warnings, budget) for v in value]
    return value


def _append_section(
    sections: list[dict[str, Any]],
    locator: dict[str, Any],
    text: str,
    warnings: list[str],
    budget: list[int],
    **fields: Any,
) -> bool:
    """Append one bounded section; return False once extraction should stop."""
    if len(sections) >= MAX_RESULT_SECTIONS:
        _add_warning(warnings, f"Result section count truncated at {MAX_RESULT_SECTIONS}")
        return False
    section: dict[str, Any] = {"locator": _bounded_field(locator, "locator", warnings, budget)}
    if len(text) > MAX_SECTION_CHARACTERS:
        text = text[:MAX_SECTION_CHARACTERS]
        _add_warning(warnings, f"Section text truncated at {MAX_SECTION_CHARACTERS} characters")
    if len(text) > budget[0]:
        text = text[:budget[0]]
        _add_warning(warnings, f"Result text truncated at {MAX_RESULT_CHARACTERS} characters")
    section["text"] = text
    budget[0] -= len(text)

    for key, value in fields.items():
        section[key] = _bounded_field(value, key, warnings, budget)
    sections.append(section)
    return budget[0] > 0 and len(sections) < MAX_RESULT_SECTIONS


def _preflight_ooxml(data: bytes, label: str) -> None:
    """Reject zip bombs and encrypted OOXML before handing bytes to parsers."""
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_OOXML_ENTRIES:
                raise ValueError(f"{label} archive has more than {MAX_OOXML_ENTRIES} entries")
            if any(entry.flag_bits & 0x1 for entry in entries):
                raise ValueError(f"Encrypted {label} archives are unsupported")
            expanded_bytes = sum(entry.file_size for entry in entries)
            if expanded_bytes > MAX_OOXML_UNCOMPRESSED_BYTES:
                raise ValueError(
                    f"{label} archive exceeds the {MAX_OOXML_UNCOMPRESSED_BYTES // (1024 * 1024)} MB expanded-size limit"
                )
    except ValueError:
        raise
    except (BadZipFile, OSError) as exc:
        raise ValueError(f"Malformed {label} archive: {exc}") from exc


def _collect(path: Path, media_type: str | None) -> tuple[str, bytes]:
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ValueError(f"Cannot read file: {exc}") from exc
    if size > MAX_FILE_BYTES:
        raise ValueError(f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MB limit")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"Cannot read file: {exc}") from exc
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MB limit")
    kind = (media_type or _MEDIA_EXTENSIONS.get(path.suffix.lower(), "")).split(";")[0].strip().lower()
    if not kind:
        raise ValueError(f"Unsupported file type: {path.suffix or '(no extension)'}")
    return kind, data


def _bounded(sections: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    # Final defense for reader branches that return an empty or unusual section.
    remaining = MAX_RESULT_CHARACTERS
    bounded_sections = []
    for section in sections[:MAX_RESULT_SECTIONS]:
        section = dict(section)
        for key, value in list(section.items()):
            if isinstance(value, str):
                limit = min(MAX_SECTION_CHARACTERS, remaining)
                if len(value) > limit:
                    section[key] = value[:limit]
                    _add_warning(warnings, f"Result text truncated at {MAX_RESULT_CHARACTERS} characters")
                remaining -= len(section[key])
        bounded_sections.append(section)
        if remaining <= 0:
            break
    if len(sections) > MAX_RESULT_SECTIONS:
        _add_warning(warnings, f"Result section count truncated at {MAX_RESULT_SECTIONS}")
    return {"sections": bounded_sections, "warnings": warnings}


def _read_eml(data: bytes) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        message = email.message_from_bytes(data, policy=policy.default)
        headers = "\n".join(f"{name}: {value}" for name, value in message.items())
        sections: list[dict[str, Any]] = []
        warnings: list[str] = []
        budget = [MAX_RESULT_CHARACTERS]
        if headers:
            if not _append_section(sections, {"part": "headers"}, headers, warnings, budget):
                return sections, warnings
        index = 0
        for part in message.walk():
            if part.is_multipart() or part.get_content_disposition() == "attachment" or part.get_filename():
                continue
            content_type = part.get_content_type()
            if content_type not in ("text/plain", "text/html"):
                continue
            try:
                body = part.get_content()
            except (LookupError, UnicodeError, email.errors.MessageError):
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                try:
                    body = payload.decode(charset, errors="replace")
                except LookupError:
                    body = payload.decode("utf-8", errors="replace")
            if isinstance(body, str) and body:
                if not _append_section(
                    sections, {"part": "body", "index": index, "content_type": content_type}, body, warnings, budget
                ):
                    break
                index += 1
        return sections, warnings
    except Exception as exc:
        raise ValueError(f"Malformed EML: {exc}") from exc


def _read_pdf(data: bytes) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        from pypdf import PdfReader

        # Many office generated PDFs have repairable xref tables. pypdf's
        # lenient mode can still extract their actual page text; unrecoverable
        # files continue to raise below.
        reader = PdfReader(BytesIO(data), strict=False)
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError(f"PDF has more than the supported {MAX_PDF_PAGES} pages")
        sections = []
        warnings = []
        budget = [MAX_RESULT_CHARACTERS]
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if not _append_section(sections, {"page": page_number}, text, warnings, budget):
                break
        if not any(section["text"].strip() for section in sections):
            warnings.append("PDF contains no extractable text (scanned pages are not OCR processed)")
        return sections, warnings
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Malformed or unreadable PDF: {exc}") from exc


def _read_xlsx(data: bytes) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        _preflight_ooxml(data, "XLSX")
        from openpyxl import load_workbook

        formulas_wb = load_workbook(BytesIO(data), data_only=False, read_only=True, keep_links=True)
        values_wb = load_workbook(BytesIO(data), data_only=True, read_only=True, keep_links=True)
        warnings: list[str] = []
        if getattr(formulas_wb, "_external_links", None):
            warnings.append("Workbook contains external links; linked content was not fetched or evaluated")
        sections = []
        budget = [MAX_RESULT_CHARACTERS]
        nonempty_cells = 0
        scanned_cells = 0
        known_functions = {"SUM", "ROUND", "ROUNDUP"}
        seen_functions: set[str] = set()
        for sheet in formulas_wb.worksheets:
            values_sheet = values_wb[sheet.title]
            row_count = sheet.max_row or 0
            column_count = sheet.max_column or 0
            if row_count * column_count > MAX_XLSX_SHEET_CELLS:
                raise ValueError(
                    f"XLSX sheet {sheet.title!r} exceeds the {MAX_XLSX_SHEET_CELLS} cell dimension limit"
                )
            scanned_cells += row_count * column_count
            if scanned_cells > MAX_XLSX_SCANNED_CELLS:
                raise ValueError(
                    f"XLSX exceeds the {MAX_XLSX_SCANNED_CELLS} scanned-cell limit"
                )
            formula_rows = sheet.iter_rows(min_row=1, max_row=row_count, min_col=1, max_col=column_count)
            value_rows = values_sheet.iter_rows(min_row=1, max_row=row_count, min_col=1, max_col=column_count)
            stop = False
            for formula_row, value_row in zip(formula_rows, value_rows):
                for cell, value_cell in zip(formula_row, value_row):
                    if cell.value is None:
                        continue
                    nonempty_cells += 1
                    if nonempty_cells > MAX_XLSX_NONEMPTY_CELLS:
                        raise ValueError(
                            f"XLSX exceeds the {MAX_XLSX_NONEMPTY_CELLS} nonempty-cell limit"
                        )
                    formula = cell.value if isinstance(cell.value, str) and cell.value.startswith("=") else None
                    cached = value_cell.value if formula else None
                    value = cached if formula else cell.value
                    parts = [f"value={_json_value(value)!r}"]
                    if formula:
                        parts.append(f"formula={formula}")
                        parts.append(f"cached_value={_json_value(cached)!r}")
                        for fn in re.findall(r"([A-Za-z_][A-Za-z0-9_.]*)\s*\(", formula):
                            upper = fn.upper()
                            if upper not in known_functions and len(seen_functions) < 100:
                                seen_functions.add(upper)
                    if not _append_section(
                        sections,
                        {"sheet": sheet.title, "cell": cell.coordinate},
                        "; ".join(parts),
                        warnings,
                        budget,
                        value=_json_value(value),
                        formula=formula,
                        cached_value=_json_value(cached) if formula else None,
                    ):
                        stop = True
                        break
                if stop:
                    break
            if stop:
                break
        if seen_functions:
            warnings.append("Unsupported formula functions found (not evaluated): " + ", ".join(sorted(seen_functions)))
        formulas_wb.close()
        values_wb.close()
        return sections, warnings
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Malformed or unreadable XLSX: {exc}") from exc


def _read_docx(data: bytes) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        _preflight_ooxml(data, "DOCX")
        from docx import Document

        document = Document(BytesIO(data))
        sections: list[dict[str, Any]] = []
        warnings: list[str] = []
        element_count = len(document.paragraphs) + sum(
            len(table.rows) * len(table.columns) for table in document.tables
        )
        if element_count > MAX_DOCX_ELEMENTS:
            raise ValueError(f"DOCX has more than the supported {MAX_DOCX_ELEMENTS} paragraphs and table cells")
        budget = [MAX_RESULT_CHARACTERS]
        for index, paragraph in enumerate(document.paragraphs):
            if paragraph.text:
                if not _append_section(
                    sections, {"type": "paragraph", "index": index}, paragraph.text, warnings, budget
                ):
                    return sections, warnings
        for table_index, table in enumerate(document.tables):
            for row_index, row in enumerate(table.rows):
                for cell_index, cell in enumerate(row.cells):
                    if cell.text:
                        if not _append_section(
                            sections,
                            {"type": "table_cell", "table": table_index, "row": row_index, "cell": cell_index},
                            cell.text,
                            warnings,
                            budget,
                        ):
                            return sections, warnings
        return sections, warnings
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Malformed or unreadable DOCX: {exc}") from exc


def read_file(path: Path, media_type: str | None = None) -> dict:
    """Read supported document text and structure without executing document content."""
    kind, data = _collect(Path(path), media_type)
    if kind in ("text/plain", "text/markdown"):
        try:
            content = data.decode("utf-8", errors="strict")
            sections, warnings = [], []
            _append_section(sections, {"line": 1}, content, warnings, [MAX_RESULT_CHARACTERS])
        except UnicodeDecodeError as exc:
            raise ValueError(f"TXT is not valid UTF-8: {exc}") from exc
        output_format = "txt"
    elif kind in ("message/rfc822", "application/vnd.ms-outlook"):
        sections, warnings = _read_eml(data)
        output_format = "eml"
    elif kind == "application/pdf":
        sections, warnings = _read_pdf(data)
        output_format = "pdf"
    elif kind == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        sections, warnings = _read_xlsx(data)
        output_format = "xlsx"
    elif kind == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        sections, warnings = _read_docx(data)
        output_format = "docx"
    else:
        raise ValueError(f"Unsupported media type: {kind}")
    bounded = _bounded(sections, warnings)
    return {"format": output_format, **bounded}
