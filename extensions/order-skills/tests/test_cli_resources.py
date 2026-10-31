import contextlib
import io
import json
from pathlib import Path
import unittest

from order_skills.__main__ import main
from order_skills.adapter import OPERATIONS
from order_skills.domain import prepare_pi
from support import order

ROOT = Path(__file__).resolve().parents[1]


class CLIResourceTests(unittest.TestCase):
    def test_examples_run_as_json(self):
        examples = {"sample-conditional": "sample_feedback", "po-missing-acceptance": "po_check",
                    "po-port-conflict": "po_check", "pi-without-approved-sample": "pi_prepare"}
        for name, operation in examples.items():
            stream = io.StringIO()
            with self.subTest(name=name), contextlib.redirect_stdout(stream):
                self.assertEqual(main([operation, str(ROOT / "examples" / f"{name}.json")]), 0)
            output = json.loads(stream.getvalue())
            self.assertEqual(output["mode"], "offline_deterministic")
            self.assertIn("analysis", output)

    def test_invalid_file_returns_json_exit_2(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(main(["po_check", str(ROOT / "examples" / "absent.json")]), 2)
        self.assertEqual(json.loads(stream.getvalue())["error"], "INVALID_INPUT")

    def test_json_schemas_validate_resources_and_results(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("Optional JSON Schema verification needs jsonschema")
        for skill, operation, filename in (("sample-feedback", "sample_feedback", "sample-conditional"),
                                            ("po-check", "po_check", "po-port-conflict"),
                                            ("pi-prepare", "pi_prepare", "pi-without-approved-sample")):
            request = json.loads((ROOT / "examples" / f"{filename}.json").read_text(encoding="utf-8"))
            for direction, instance in (("input", request), ("output", OPERATIONS[operation](request))):
                schema = json.loads((ROOT / "skills" / skill / f"{direction}.schema.json").read_text(encoding="utf-8"))
                Draft202012Validator.check_schema(schema)
                Draft202012Validator(schema).validate(instance)
        schema = json.loads((ROOT / "skills/pi-prepare/output.schema.json").read_text(encoding="utf-8"))
        forged = prepare_pi(order())
        forged["payment_received"] = True
        self.assertFalse(Draft202012Validator(schema).is_valid(forged))


if __name__ == "__main__":
    unittest.main()
