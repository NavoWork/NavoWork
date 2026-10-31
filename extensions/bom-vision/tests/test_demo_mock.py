import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from bom_vision import correct, revalidate
from bom_vision.mock import mock_recognize
from bom_vision.mock_cli import main as bom_main
from demo_mock import Catalog, MockError, fingerprint
from demo_mock.catalog import decode_json
from demo_mock.cli import main

ROOT = Path(__file__).resolve().parents[1]
BOM_CATALOG = ROOT / "samples/mock.catalog.json"
DOCUMENT_CATALOG = ROOT / "examples/document-demo/catalog.json"


class CatalogTests(unittest.TestCase):
    def test_json_key_order_ignored_but_values_and_types_matter(self):
        self.assertEqual(fingerprint({"a": 1, "b": [False, None]}), fingerprint({"b": [False, None], "a": 1}))
        self.assertNotEqual(fingerprint({"a": 1}), fingerprint({"a": "1"}))
        self.assertNotEqual(fingerprint(1), fingerprint(1.0))
        self.assertNotEqual(fingerprint(b"null"), fingerprint(None))
        self.assertNotEqual(fingerprint([1, 2]), fingerprint([2, 1]))

    def test_invalid_json_inputs_are_rejected(self):
        for value in (float("nan"), float("inf"), {1: "ambiguous key"}, (1, 2), {1, 2}, object()):
            with self.assertRaises(MockError):
                fingerprint(value)
        recursive = []
        recursive.append(recursive)
        with self.assertRaisesRegex(MockError, "mock_json_too_deep"):
            fingerprint(recursive)
        with self.assertRaisesRegex(MockError, "mock_json_duplicate_key"):
            decode_json(b'{"a":1,"a":2}')

    def test_stateless_multi_step_json_replay_and_isolation(self):
        catalog = Catalog.load(DOCUMENT_CATALOG)
        request = {"language": "zh", "document_type": "specification"}
        first = catalog.replay("document-demo", "summarize", {"request": request})
        second = catalog.replay("document-demo", "next-actions", {"summary": first["data"]})
        self.assertEqual(second["data"]["status"], "draft")
        first["data"]["missing_fields"].clear()
        self.assertEqual(len(catalog.replay("document-demo", "summarize", {"request": request})["data"]["missing_fields"]), 2)
        self.assertEqual(second["mode"], "mock")
        self.assertEqual(catalog.check()["scenario_count"], 2)

    def test_scope_and_exact_named_inputs_no_wildcards(self):
        catalog = Catalog.load(DOCUMENT_CATALOG)
        request = {"document_type": "specification", "language": "zh"}
        for workflow, operation, inputs in (
            ("other", "summarize", {"request": request}),
            ("document-demo", "other", {"request": request}),
            ("document-demo", "summarize", {"wrong_name": request}),
            ("document-demo", "summarize", {"request": request, "extra": True}),
            ("document-demo", "summarize", {"request": {"language": "en"}}),
        ):
            with self.assertRaisesRegex(MockError, "mock_sample_not_found"):
                catalog.replay(workflow, operation, inputs)

    def test_duplicate_matches_and_ids_fail_closed(self):
        original = json.loads(DOCUMENT_CATALOG.read_text(encoding="utf-8"))
        for same_id, code in ((False, "mock_match_ambiguous"), (True, "mock_scenario_id_duplicate")):
            doc = copy.deepcopy(original)
            row = copy.deepcopy(doc["scenarios"][0])
            if not same_id:
                row["id"] = "duplicate-with-different-id"
            doc["scenarios"].append(row)
            with self.assertRaisesRegex(MockError, code):
                Catalog(doc, DOCUMENT_CATALOG.parent)

    def test_multiple_named_inputs_are_all_required(self):
        doc = json.loads(DOCUMENT_CATALOG.read_text(encoding="utf-8"))
        row = doc["scenarios"][0]
        row["inputs"]["attachment"] = fingerprint(b"exact attachment")
        catalog = Catalog(doc, DOCUMENT_CATALOG.parent)
        inputs = {"request": {"document_type": "specification", "language": "zh"}, "attachment": b"exact attachment"}
        self.assertEqual(catalog.replay("document-demo", "summarize", inputs)["mock"]["scenario_id"], "summary-zh")
        del inputs["attachment"]
        with self.assertRaisesRegex(MockError, "mock_sample_not_found"):
            catalog.replay("document-demo", "summarize", inputs)

    def test_fixture_pin_ignores_formatting_but_detects_semantic_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixture.json"
            value = {"number": "3.50", "unit": "m"}
            fixture.write_text(json.dumps(value, indent=4), encoding="utf-8")
            doc = {"schema_version": 1, "catalog_id": "test", "scenarios": [
                {"id": "one", "workflow": "test", "operation": "extract", "inputs": {"image": fingerprint(b"file")},
                 "output": {"path": fixture.name, "sha256": fingerprint(value)["sha256"]}}]}
            catalog = Catalog(doc, root)
            catalog.check()
            fixture.write_text('{"unit":"m","number":"3.50"}\r\n', encoding="utf-8")
            catalog.check()
            fixture.write_text('{"unit":"m","number":"4.50"}', encoding="utf-8")
            with self.assertRaisesRegex(MockError, "mock_output_hash_mismatch"):
                catalog.replay("test", "extract", {"image": b"file"})

    def test_schema_path_and_missing_fixture_validation(self):
        original = json.loads(DOCUMENT_CATALOG.read_text(encoding="utf-8"))
        doc = copy.deepcopy(original)
        doc["schema_version"] = True
        with self.assertRaisesRegex(MockError, "mock_catalog_version_unsupported"):
            Catalog(doc, DOCUMENT_CATALOG.parent)
        doc = copy.deepcopy(original)
        doc["scenarios"][0]["output"]["path"] = "../outside.json"
        with self.assertRaisesRegex(MockError, "mock_output_path_outside_catalog"):
            Catalog(doc, DOCUMENT_CATALOG.parent)
        doc["scenarios"][0]["output"]["path"] = "missing.json"
        with self.assertRaisesRegex(MockError, "mock_file_unavailable"):
            Catalog(doc, DOCUMENT_CATALOG.parent).check()


class BomMockTests(unittest.TestCase):
    def test_all_bom_fixtures_without_model_and_existing_corrections(self):
        manifest = json.loads((ROOT / "samples/manifest.json").read_text())
        catalog = Catalog.load(BOM_CATALOG)
        with patch("bom_vision.adapters.OpenAICompatibleAdapter.from_environment", side_effect=AssertionError("model forbidden")), \
             patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("network forbidden")):
            results = {}
            for name, item in manifest.items():
                result = mock_recognize((ROOT / "samples" / item["image"]).read_bytes(),
                                        {"file_id": "uploaded-now", "case_id": "runtime-case"}, catalog=catalog)
                self.assertEqual(result["rows"][0]["quantity"], item["expected_quantity"])
                self.assertEqual(result["table_total"], item["expected_total"])
                self.assertEqual(result["mock"]["scenario_id"], name)
                self.assertEqual(result["mode"], "mock")
                self.assertEqual(result["recognition"]["adapter"], "mock-fixture-replay")
                self.assertEqual(result["source"]["file_ref"]["file_id"], "uploaded-now")
                self.assertFalse(result["validation"]["price_approved"])
                self.assertEqual(result, revalidate(result))
                results[name] = result
            edited = correct(results["total_conflict"], [{"row_id": None, "field": "table_total", "value": "36.00"}],
                             expected_revision=1, actor="reviewer", reason="demo correction")
            self.assertNotIn("table_total_mismatch", {i["code"] for i in edited["issues"]})
            self.assertEqual(edited["mock"], results["total_conflict"]["mock"])
            self.assertEqual(edited["revision"], 2)
            self.assertIsNone(results["missing_price"]["rows"][0]["unit_price"])
            self.assertIn("quantity", results["blurry_digit"]["rows"][0]["uncertain_fields"])

    def test_modified_image_never_falls_back(self):
        image = (ROOT / "samples/clear.jpg").read_bytes()
        with self.assertRaisesRegex(MockError, "mock_sample_not_found"):
            mock_recognize(image + b"different bytes", {"file_id": "new"}, catalog=Catalog.load(BOM_CATALOG))

    def test_same_image_runtime_references_do_not_leak_between_cases(self):
        catalog = Catalog.load(BOM_CATALOG)
        image = (ROOT / "samples/clear.jpg").read_bytes()
        a = mock_recognize(image, {"case_id": "a", "file_id": "a1"}, catalog=catalog)
        b = mock_recognize(image, {"case_id": "b", "file_id": "b1"}, catalog=catalog)
        self.assertNotEqual(a["source"]["file_ref"], b["source"]["file_ref"])
        self.assertEqual(a["mock"], b["mock"])


class MockCliTests(unittest.TestCase):
    def call(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_authoring_then_replay_and_duplicate_add_no_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "out.json"
            fixture.write_text('{"status":"draft"}', encoding="utf-8")
            attachment = root / "input.bin"
            attachment.write_bytes(b"example attachment")
            catalog = root / "catalog.json"
            args = ["add", "--catalog", str(catalog), "--catalog-id", "new-demo-v1", "--scenario", "one",
                    "--workflow", "new-demo", "--operation", "preview", "--file", f"attachment={attachment}", "--output", str(fixture)]
            self.assertEqual(self.call(args)[0], 0)
            before = catalog.read_bytes()
            self.assertEqual(self.call(args)[0], 2)
            self.assertEqual(before, catalog.read_bytes())
            code, out, _ = self.call(["run", "--catalog", str(catalog), "--workflow", "new-demo",
                                      "--operation", "preview", "--file", f"attachment={attachment}"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out)["data"], {"status": "draft"})
            self.assertEqual(self.call(["check", "--catalog", str(catalog)])[0], 0)

    def test_json_fingerprint_cli_and_duplicate_input_names(self):
        request = ROOT / "examples/document-demo/request.json"
        code, out, _ = self.call(["fingerprint", "--json", f"request={request}"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["request"]["kind"], "json-v1")
        code, _, err = self.call(["fingerprint", "--json", f"request={request}", "--file", f"request={request}"])
        self.assertEqual(code, 2)
        self.assertIn("mock_input_argument_invalid", err)

    def test_generic_and_bom_cli_outputs_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "result.json"
            argv = ["run", "--catalog", str(DOCUMENT_CATALOG), "--workflow", "document-demo",
                    "--operation", "summarize", "--json", f"request={ROOT / 'examples/document-demo/request.json'}", "--out", str(output)]
            self.assertEqual(self.call(argv)[0], 0)
            self.assertEqual(self.call(argv)[0], 2)
            output = Path(tmp) / "bom.json"
            args = [str(ROOT / "samples/clear.jpg"), "--catalog", str(BOM_CATALOG), "--out", str(output)]
            with redirect_stderr(io.StringIO()):
                self.assertEqual(bom_main(args), 0)
                self.assertEqual(bom_main(args), 2)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["mode"], "mock")
