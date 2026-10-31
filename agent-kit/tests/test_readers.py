from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path
from io import BytesIO
import sys
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import Workbook
from docx import Document

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from navowork_agent.tools.readers import read_file  # noqa: E402


class ReadFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, name: str, data: bytes) -> Path:
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_txt_is_utf8_and_character_bounded(self) -> None:
        result = read_file(self.write("note.txt", "报价说明：颜色为海军蓝".encode("utf-8")))
        self.assertEqual(result["format"], "txt")
        self.assertIn("颜色为海军蓝", result["sections"][0]["text"])
        self.assertEqual(result["sections"][0]["locator"], {"line": 1})

        long_result = read_file(self.write("long.txt", ("好" * 100_005).encode("utf-8")))
        self.assertEqual(len(long_result["sections"][0]["text"]), 10_000)
        self.assertTrue(any("truncated" in warning for warning in long_result["warnings"]))

    def test_eml_decodes_headers_and_body_but_skips_attachment_content(self) -> None:
        msg = EmailMessage()
        msg["From"] = "供应商 <factory@example.invalid>"
        msg["Subject"] = "彩盒价格确认"
        msg.set_content("附件中的数据仍然只是邮件内容。")
        msg.add_attachment(b"HIDDEN ATTACHMENT", maintype="application", subtype="octet-stream", filename="secret.bin")
        result = read_file(self.write("mail.eml", msg.as_bytes()))
        joined = "\n".join(section["text"] for section in result["sections"])
        self.assertIn("Subject: 彩盒价格确认", joined)
        self.assertIn("附件中的数据仍然只是邮件内容。", joined)
        self.assertNotIn("HIDDEN ATTACHMENT", joined)
        self.assertEqual(result["format"], "eml")

    def test_pdf_reports_page_number_locators_for_real_fixture(self) -> None:
        fixture = Path(__file__).resolve().parents[2] / "test" / "inputs" / "BAG-2026-DE-003" / "supplier-reply.pdf"
        if not fixture.exists():
            self.skipTest("repository PDF fixture is unavailable")
        result = read_file(fixture)
        self.assertTrue(result["sections"])
        self.assertEqual(result["sections"][0]["locator"]["page"], 1)
        self.assertTrue(any(section["text"].strip() for section in result["sections"]))

    def test_xlsx_returns_actual_cell_values_formulas_and_cached_value(self) -> None:
        path = self.root / "cost.xlsx"
        book = Workbook()
        sheet = book.active
        sheet.title = "Costs"
        sheet["A1"] = "unit cost"
        sheet["B1"] = 12.75
        sheet["C1"] = "=SUM(B1,2)"
        sheet["D1"] = "=NOW()"
        book.save(path)

        result = read_file(path)
        cells = {section["locator"]["cell"]: section for section in result["sections"]}
        self.assertEqual(cells["B1"]["value"], 12.75)
        self.assertEqual(cells["C1"]["formula"], "=SUM(B1,2)")
        self.assertIn("cached_value", cells["C1"])
        self.assertIsNone(cells["C1"]["cached_value"])  # openpyxl does not calculate formulas
        self.assertTrue(any("NOW" in warning and "not evaluated" in warning for warning in result["warnings"]))

        sheet["B1"] = 19.5
        book.save(path)
        changed = read_file(path)
        changed_cells = {section["locator"]["cell"]: section for section in changed["sections"]}
        self.assertEqual(changed_cells["B1"]["value"], 19.5)
        self.assertNotEqual(changed_cells["B1"]["value"], cells["B1"]["value"])

    def test_xlsx_limits_dimension_and_bounds_large_cell_strings(self) -> None:
        huge = Workbook()
        huge.active["XFD1048576"] = "last cell"
        huge_path = self.root / "huge-dimension.xlsx"
        huge.save(huge_path)
        with self.assertRaisesRegex(ValueError, "dimension limit"):
            read_file(huge_path)

        strings = Workbook()
        strings.active["A1"] = "v" * 20_000
        string_path = self.root / "long-value.xlsx"
        strings.save(string_path)
        result = read_file(string_path)
        section = result["sections"][0]
        self.assertLessEqual(len(section["text"]), 10_000)
        self.assertLessEqual(len(section["value"]), 10_000)
        self.assertTrue(any("truncated" in warning for warning in result["warnings"]))

    def test_ooxml_preflight_rejects_zip_bomb_metadata(self) -> None:
        archive_bytes = BytesIO()
        with ZipFile(archive_bytes, "w", compression=ZIP_DEFLATED) as archive:
            # Small compressed payload with expanded size above the 64 MiB cap.
            archive.writestr("xl/worksheets/sheet1.xml", b"x" * (64 * 1024 * 1024 + 1))
        path = self.write("zip-bomb.xlsx", archive_bytes.getvalue())
        with self.assertRaisesRegex(ValueError, "expanded-size limit"):
            read_file(path)

    def test_docx_exposes_paragraph_and_table_cell_locations(self) -> None:
        doc = Document()
        doc.add_paragraph("实际规格：海军蓝")
        table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "数量"
        table.cell(0, 1).text = "3000"
        path = self.root / "spec.docx"
        doc.save(path)
        result = read_file(path)
        by_text = {section["text"]: section["locator"] for section in result["sections"]}
        self.assertEqual(by_text["实际规格：海军蓝"], {"type": "paragraph", "index": 0})
        self.assertEqual(by_text["3000"], {"type": "table_cell", "table": 0, "row": 0, "cell": 1})

    def test_docx_and_pdf_explicitly_reject_excessive_structure(self) -> None:
        doc = Document()
        for _ in range(10_001):
            doc.add_paragraph("x")
        docx_path = self.root / "too-many-paragraphs.docx"
        doc.save(docx_path)
        with self.assertRaisesRegex(ValueError, "paragraphs and table cells"):
            read_file(docx_path)

        from pypdf import PdfWriter

        writer = PdfWriter()
        for _ in range(101):
            writer.add_blank_page(width=72, height=72)
        pdf_data = BytesIO()
        writer.write(pdf_data)
        with self.assertRaisesRegex(ValueError, "supported 100 pages"):
            read_file(self.write("too-many-pages.pdf", pdf_data.getvalue()))

    def test_unsupported_malformed_and_oversize_inputs_explain_failure(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported file type"):
            read_file(self.write("image.png", b"png"))
        with self.assertRaisesRegex(ValueError, "not valid UTF-8"):
            read_file(self.write("bad.txt", b"\xff"))
        with self.assertRaisesRegex(ValueError, "Malformed XLSX archive"):
            read_file(self.write("broken.xlsx", b"not a spreadsheet"))
        oversized = self.write("large.txt", b"x" * (20 * 1024 * 1024 + 1))
        with self.assertRaisesRegex(ValueError, "20 MB limit"):
            read_file(oversized)


if __name__ == "__main__":
    unittest.main()
