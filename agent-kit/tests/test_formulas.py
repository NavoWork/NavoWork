from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys
import unittest

from openpyxl import Workbook, load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from navowork_agent.tools.formulas import recalculate_xlsx  # noqa: E402


def workbook_bytes(setup) -> bytes:
    workbook = Workbook()
    setup(workbook.active)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


class RecalculateXlsxTests(unittest.TestCase):
    def test_nested_arithmetic_sum_rounding_and_cache_refresh(self) -> None:
        def setup(sheet):
            sheet["A1"] = 1.25
            sheet["A2"] = 2.25
            sheet["A3"] = 3.5
            sheet["B1"] = "=(SUM(A1:A3) + 2) * 2"
            sheet["B2"] = "=ROUND(-1.25,1)"
            sheet["B3"] = "=ROUNDUP(-1.21,1)"

        original = workbook_bytes(setup)
        recalculated = recalculate_xlsx(original)
        formula_wb = load_workbook(BytesIO(recalculated), data_only=False)
        value_wb = load_workbook(BytesIO(recalculated), data_only=True)
        self.assertEqual(formula_wb.active["B1"].value, "=(SUM(A1:A3) + 2) * 2")
        self.assertEqual(value_wb.active["B1"].value, 18)
        self.assertEqual(value_wb.active["B2"].value, -1.3)
        self.assertEqual(value_wb.active["B3"].value, -1.3)
        formula_wb.close()
        value_wb.close()

        changed = load_workbook(BytesIO(original))
        changed.active["A1"] = 5
        output = BytesIO()
        changed.save(output)
        changed.close()
        refreshed = load_workbook(BytesIO(recalculate_xlsx(output.getvalue())), data_only=True)
        self.assertEqual(refreshed.active["B1"].value, 25.5)
        refreshed.close()

    def test_cycle_is_rejected(self) -> None:
        data = workbook_bytes(lambda sheet: (setattr(sheet["A1"], "value", "=B1+1"), setattr(sheet["B1"], "value", "=A1+1")))
        with self.assertRaisesRegex(ValueError, "cycle"):
            recalculate_xlsx(data)

    def test_unknown_functions_external_and_cross_sheet_refs_are_rejected(self) -> None:
        for formula, expected in [("=NOW()", "Unsupported formula function"), ("=Other!A1+1", "Cross-sheet"), ("='[book.xlsx]Sheet1'!A1", "Cross-sheet")]:
            with self.subTest(formula=formula):
                data = workbook_bytes(lambda sheet: setattr(sheet["A1"], "value", formula))
                with self.assertRaisesRegex(ValueError, expected):
                    recalculate_xlsx(data)

    def test_missing_and_non_numeric_inputs_are_rejected(self) -> None:
        for input_value, message in [(None, "Missing input"), ("not a number", "Non-numeric input")]:
            with self.subTest(input_value=input_value):
                def setup(sheet):
                    sheet["A1"] = input_value
                    sheet["B1"] = "=A1+1"
                with self.assertRaisesRegex(ValueError, message):
                    recalculate_xlsx(workbook_bytes(setup))

    def test_range_and_workload_limits_are_enforced(self) -> None:
        data = workbook_bytes(lambda sheet: setattr(sheet["A1"], "value", "=SUM(A1:A1001)"))
        with self.assertRaisesRegex(ValueError, "range exceeds"):
            recalculate_xlsx(data)
        deep = workbook_bytes(lambda sheet: setattr(sheet["A1"], "value", "=" + "(" * 35 + "1" + ")" * 35))
        with self.assertRaisesRegex(ValueError, "nesting depth"):
            recalculate_xlsx(deep)


if __name__ == "__main__":
    unittest.main()
