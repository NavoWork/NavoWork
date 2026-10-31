"""Bounded evaluator for a small, deterministic subset of XLSX formulas."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_UP, localcontext
from io import BytesIO
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET

MAX_XLSX_BYTES = 20 * 1024 * 1024
MAX_WORKBOOK_CELLS = 100_000
MAX_FORMULA_LENGTH = 512
MAX_PARSE_DEPTH = 32
MAX_RANGE_CELLS = 1_000

_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_REL_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
_CELL_REF = re.compile(r"([A-Z]{1,3})([1-9][0-9]{0,6})\Z", re.I)
_TOKEN = re.compile(
    r"\s*(?:(\d+(?:\.\d*)?|\.\d+)|([A-Za-z_][A-Za-z0-9_.]*)|(:)|([()+\-*/,]))"
)


def _column_number(letters: str) -> int:
    result = 0
    for char in letters.upper():
        result = result * 26 + ord(char) - 64
    return result


def _coordinate(text: str) -> tuple[int, int]:
    match = _CELL_REF.fullmatch(text)
    if not match:
        raise ValueError(f"Unsupported cell reference: {text}")
    return int(match.group(2)), _column_number(match.group(1))


class _Parser:
    def __init__(self, formula: str, resolve_cell, resolve_range) -> None:
        if len(formula) > MAX_FORMULA_LENGTH:
            raise ValueError("Formula exceeds the supported length limit")
        if not formula.startswith("="):
            raise ValueError("Expected a formula starting with '='")
        if "!" in formula or "[" in formula or "]" in formula or "$" in formula:
            raise ValueError("Cross-sheet, external, and absolute references are unsupported")
        self.tokens: list[tuple[str, str]] = []
        source = formula[1:]
        pos = 0
        while pos < len(source):
            if source[pos:].isspace():
                break
            match = _TOKEN.match(source, pos)
            if not match:
                raise ValueError(f"Unsupported formula syntax near {source[pos:pos + 20]!r}")
            number, name, colon, punctuation = match.groups()
            token = number or name or colon or punctuation
            kind = "number" if number else "name" if name else token
            self.tokens.append((kind, token))
            pos = match.end()
        self.index = 0
        self.depth = 0
        self.resolve_cell = resolve_cell
        self.resolve_range = resolve_range

    def _peek(self, value: str | None = None) -> bool:
        if self.index >= len(self.tokens):
            return False
        return value is None or self.tokens[self.index][1] == value

    def _take(self) -> tuple[str, str]:
        if not self._peek():
            raise ValueError("Unexpected end of formula")
        token = self.tokens[self.index]
        self.index += 1
        return token

    def parse(self) -> Decimal:
        result = self._expression()
        if self._peek():
            raise ValueError(f"Unexpected token {self.tokens[self.index][1]!r}")
        return result

    def _expression(self) -> Decimal:
        result = self._term()
        while self._peek("+") or self._peek("-"):
            op = self._take()[1]
            right = self._term()
            result = result + right if op == "+" else result - right
        return result

    def _term(self) -> Decimal:
        result = self._unary()
        while self._peek("*") or self._peek("/"):
            op = self._take()[1]
            right = self._unary()
            if op == "/" and right == 0:
                raise ValueError("Division by zero")
            result = result * right if op == "*" else result / right
        return result

    def _unary(self, depth: int = 0) -> Decimal:
        if depth > MAX_PARSE_DEPTH:
            raise ValueError("Formula exceeds the supported nesting depth")
        if self._peek("+"):
            self._take()
            return self._unary(depth + 1)
        if self._peek("-"):
            self._take()
            return -self._unary(depth + 1)
        return self._primary()

    def _primary(self) -> Decimal:
        self.depth += 1
        if self.depth > MAX_PARSE_DEPTH:
            raise ValueError("Formula exceeds the supported nesting depth")
        try:
            if self._peek("("):
                self._take()
                result = self._expression()
                if not self._peek(")"):
                    raise ValueError("Missing closing parenthesis")
                self._take()
                return result
            kind, value = self._take()
            if kind == "number":
                return Decimal(value)
            if kind != "name":
                raise ValueError(f"Unexpected token {value!r}")
            if self._peek("("):
                return self._function(value.upper())
            if _CELL_REF.fullmatch(value):
                return self.resolve_cell(value.upper())
            raise ValueError(f"Unsupported name or function: {value}")
        finally:
            self.depth -= 1

    def _function(self, name: str) -> Decimal:
        if name not in {"SUM", "ROUND", "ROUNDUP"}:
            raise ValueError(f"Unsupported formula function: {name}")
        self._take()  # (
        if name == "SUM":
            start_kind, start = self._take()
            if start_kind != "name" or not _CELL_REF.fullmatch(start):
                raise ValueError("SUM supports a single cell range")
            if not self._peek(":"):
                raise ValueError("SUM requires a range such as SUM(A1:A3)")
            self._take()
            end_kind, end = self._take()
            if end_kind != "name" or not _CELL_REF.fullmatch(end):
                raise ValueError("Invalid SUM range")
            if not self._peek(")"):
                raise ValueError("SUM supports a single cell range")
            self._take()
            return self.resolve_range(start.upper(), end.upper())
        value = self._expression()
        if not self._peek(","):
            raise ValueError(f"{name} requires a digits argument")
        self._take()
        sign = 1
        if self._peek("-"):
            self._take()
            sign = -1
        elif self._peek("+"):
            self._take()
        kind, digits_text = self._take()
        if kind != "number" or not re.fullmatch(r"\d{1,2}", digits_text):
            raise ValueError(f"{name} digits must be an integer from -99 to 99")
        digits = sign * int(digits_text)
        if not self._peek(")"):
            raise ValueError(f"Unexpected argument to {name}")
        self._take()
        quantum = Decimal(1).scaleb(-digits)
        mode = ROUND_HALF_UP if name == "ROUND" else ROUND_UP
        try:
            return value.quantize(quantum, rounding=mode)
        except InvalidOperation as exc:
            raise ValueError("ROUND result is outside the supported numeric range") from exc


def _decimal(value, coordinate: str) -> Decimal:
    if value is None:
        raise ValueError(f"Missing input value at {coordinate}")
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"Non-numeric input at {coordinate}")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Non-numeric input at {coordinate}") from exc
    if not result.is_finite():
        raise ValueError(f"Non-finite input at {coordinate}")
    return result


def _sheet_parts(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    try:
        root = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    except (KeyError, ET.ParseError) as exc:
        raise ValueError(f"Malformed XLSX workbook metadata: {exc}") from exc
    targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall(f"{{{_REL_PKG}}}Relationship")}
    parts = []
    for sheet in root.findall(f".//{{{_MAIN}}}sheet"):
        rel_id = sheet.attrib.get(f"{{{_REL_DOC}}}id")
        if rel_id not in targets:
            raise ValueError("Malformed XLSX worksheet relationship")
        target = targets[rel_id]
        path = posixpath.normpath(target.lstrip("/") if target.startswith("/") else posixpath.join("xl", target))
        parts.append((sheet.attrib["name"], path))
    return parts


def recalculate_xlsx(data: bytes) -> bytes:
    """Evaluate supported formulas and patch their cached values in XLSX bytes."""
    if not isinstance(data, bytes):
        raise ValueError("XLSX input must be bytes")
    if len(data) > MAX_XLSX_BYTES:
        raise ValueError("XLSX exceeds the 20 MB limit")
    try:
        from openpyxl import load_workbook

        source = BytesIO(data)
        wb = load_workbook(source, data_only=False, read_only=False, keep_links=True)
    except Exception as exc:
        raise ValueError(f"Malformed or unreadable XLSX: {exc}") from exc
    try:
        if getattr(wb, "_external_links", None):
            raise ValueError("External links are unsupported")
        cell_count = sum(len(sheet._cells) for sheet in wb.worksheets)
        if cell_count > MAX_WORKBOOK_CELLS:
            raise ValueError("Workbook exceeds the supported cell limit")
        formulas: dict[tuple[str, str], str] = {}
        values: dict[tuple[str, str], object] = {}
        for sheet in wb.worksheets:
            for cell in sheet._cells.values():
                key = (sheet.title, cell.coordinate)
                if cell.data_type == "f" or (isinstance(cell.value, str) and cell.value.startswith("=")):
                    if not isinstance(cell.value, str):
                        raise ValueError(f"Unsupported formula encoding at {sheet.title}!{cell.coordinate}")
                    formulas[key] = cell.value
                else:
                    values[key] = cell.value
        calculated: dict[tuple[str, str], Decimal] = {}
        visiting: set[tuple[str, str]] = set()

        def evaluate(sheet_name: str, coordinate: str) -> Decimal:
            key = (sheet_name, coordinate)
            if key in calculated:
                return calculated[key]
            if key in visiting:
                raise ValueError(f"Formula cycle detected at {sheet_name}!{coordinate}")
            if key not in formulas:
                return _decimal(values.get(key), f"{sheet_name}!{coordinate}")
            visiting.add(key)
            try:
                result = _Parser(
                    formulas[key],
                    lambda ref: evaluate(sheet_name, ref),
                    lambda start, end: sum_range(sheet_name, start, end),
                ).parse()
                if not result.is_finite():
                    raise ValueError(f"Non-finite formula result at {sheet_name}!{coordinate}")
                calculated[key] = result
                return result
            except (InvalidOperation, OverflowError, ZeroDivisionError) as exc:
                raise ValueError(f"Cannot calculate formula at {sheet_name}!{coordinate}: {exc}") from exc
            finally:
                visiting.remove(key)

        def sum_range(sheet_name: str, start: str, end: str) -> Decimal:
            row1, col1 = _coordinate(start)
            row2, col2 = _coordinate(end)
            min_row, max_row = sorted((row1, row2))
            min_col, max_col = sorted((col1, col2))
            count = (max_row - min_row + 1) * (max_col - min_col + 1)
            if count > MAX_RANGE_CELLS:
                raise ValueError("SUM range exceeds the supported size limit")
            total = Decimal(0)
            from openpyxl.utils import get_column_letter
            for row in range(min_row, max_row + 1):
                for col in range(min_col, max_col + 1):
                    total += evaluate(sheet_name, f"{get_column_letter(col)}{row}")
            return total

        with localcontext() as context:
            context.prec = 50
            for sheet_name, coordinate in formulas:
                evaluate(sheet_name, coordinate)

        updated: dict[str, bytes] = {}
        with zipfile.ZipFile(BytesIO(data), "r") as archive:
            sheet_paths = _sheet_parts(archive)
            for sheet_name, path in sheet_paths:
                root = ET.fromstring(archive.read(path))
                for cell in root.findall(f".//{{{_MAIN}}}c"):
                    coordinate = cell.attrib.get("r")
                    key = (sheet_name, coordinate or "")
                    if key not in calculated:
                        continue
                    value_node = cell.find(f"{{{_MAIN}}}v")
                    if value_node is None:
                        value_node = ET.SubElement(cell, f"{{{_MAIN}}}v")
                    value_node.text = str(calculated[key])
                    cell.attrib.pop("t", None)
                updated[path] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
            calc = workbook_root.find(f"{{{_MAIN}}}calcPr")
            if calc is None:
                calc = ET.SubElement(workbook_root, f"{{{_MAIN}}}calcPr")
            calc.set("fullCalcOnLoad", "1")
            calc.set("forceFullCalc", "1")
            calc.set("calcMode", "auto")
            updated["xl/workbook.xml"] = ET.tostring(workbook_root, encoding="utf-8", xml_declaration=True)
            output = BytesIO()
            with zipfile.ZipFile(output, "w") as target:
                for info in archive.infolist():
                    target.writestr(info, updated.get(info.filename, archive.read(info.filename)))
        return output.getvalue()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Malformed or unreadable XLSX: {exc}") from exc
    finally:
        wb.close()
