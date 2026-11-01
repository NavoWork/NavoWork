import base64
import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from PIL import Image

from bom_vision import InputError, correct, recognize, revalidate
from bom_vision.adapters import AdapterError, OpenAICompatibleAdapter, _post
from bom_vision.cli import main
from bom_vision.core import MAX_BYTES, inspect_image, parse_response
from bom_vision.integration import recognize_tool

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
MANIFEST = json.loads((SAMPLES / "manifest.json").read_text())
REF = {"id": "file-test", "version": "version-1", "case_id": "case-a"}


class HashBoundFake:
    name = "FAKE-replay-not-vision"

    def __init__(self, sample):
        self.sample = MANIFEST[sample]

    def extract(self, image, mime_type):
        if hashlib.sha256(image).hexdigest() != self.sample["sha256"]:
            raise AdapterError("fake_image_hash_mismatch")
        return (SAMPLES / self.sample["fake_response"]).read_text(encoding="utf-8")


def sample(name="clear"):
    return recognize((SAMPLES / MANIFEST[name]["image"]).read_bytes(), REF, HashBoundFake(name))


def codes(candidate):
    return {issue["code"] for issue in candidate["issues"]}


class CoreTests(unittest.TestCase):
    def test_clear_decimal_provenance_and_still_candidate(self):
        result = sample()
        self.assertEqual(result["rows"][0]["quantity"], "2.50")
        self.assertEqual(result["validation"]["subtotal_sums_by_currency"], {"CNY": "36.00"})
        self.assertEqual(result["issues"], [])
        self.assertTrue(result["validation"]["needs_review"])
        self.assertFalse(result["validation"]["price_approved"])
        self.assertEqual(result["status"], "candidate")
        self.assertEqual(result["source"]["file_ref"], REF)
        self.assertEqual(result["source"]["sha256"], MANIFEST["clear"]["sha256"])
        self.assertEqual(result["rows"][0]["source"]["kind"], "visual_row_text")
        self.assertIn("Nylon", result["recognition"]["raw_response"])
        self.assertEqual(result, revalidate(result))

    def test_missing_price_is_not_invented(self):
        result = sample("missing_price")
        self.assertIsNone(result["rows"][0]["unit_price"])
        self.assertIsNone(result["rows"][0]["subtotal"])
        self.assertIn("missing_field", codes(result))
        self.assertIn("total_not_comparable", codes(result))

    def test_blurry_digit_stays_uncertain(self):
        result = sample("blurry_digit")
        self.assertIsNone(result["rows"][0]["quantity"])
        self.assertIn("uncertain_value", codes(result))
        self.assertIn("2.?0", result["rows"][0]["source"]["raw_text"])

    def test_total_conflict(self):
        self.assertIn("table_total_mismatch", codes(sample("total_conflict")))

    def test_real_pixels_changed_and_replay_explicitly_not_vision(self):
        original = (SAMPLES / MANIFEST["clear"]["image"]).read_bytes()
        changed = (SAMPLES / MANIFEST["changed_number"]["image"]).read_bytes()
        with Image.open(io.BytesIO(original)) as a, Image.open(io.BytesIO(changed)) as b:
            self.assertNotEqual(a.tobytes(), b.tobytes())
        with self.assertRaisesRegex(AdapterError, "fake_image_hash_mismatch"):
            recognize(changed, REF, HashBoundFake("clear"))
        self.assertNotEqual(sample()["rows"][0]["quantity"], sample("changed_number")["rows"][0]["quantity"])

    def test_atomic_correction_revision_and_evidence(self):
        original = sample("blurry_digit")
        edited = correct(original, [{"row_id": "row-1", "field": "quantity", "value": "25"}],
                         expected_revision=1, actor="reviewer", reason="checked original")
        self.assertEqual(edited["revision"], 2)
        self.assertEqual(edited["rows"][0]["uncertain_fields"], [])
        self.assertIn("row_amount_mismatch", codes(edited))
        self.assertEqual(edited["recognition"], original["recognition"])
        self.assertEqual(edited["rows"][0]["source"], original["rows"][0]["source"])
        self.assertEqual(edited["corrections"][0]["before"], None)
        self.assertEqual(original["revision"], 1)
        with self.assertRaisesRegex(InputError, "revision_conflict"):
            correct(edited, [], expected_revision=1, actor="x", reason="x")
        with self.assertRaisesRegex(InputError, "invalid_patch_target"):
            correct(original, [{"row_id": "row-1", "field": "quantity", "value": "2"},
                               {"row_id": "row-1", "field": "source", "value": "forged"}],
                    expected_revision=1, actor="x", reason="x")
        self.assertIsNone(original["rows"][0]["quantity"])

    def test_total_correction_not_approval(self):
        edited = correct(sample("total_conflict"), [{"row_id": None, "field": "table_total", "value": "36.00"}],
                         expected_revision=1, actor="human", reason="read total")
        self.assertNotIn("table_total_mismatch", codes(edited))
        self.assertFalse(edited["validation"]["price_approved"])
        self.assertEqual(edited["recognition"]["original_extraction"]["table_total"], "39.00")

    def test_numeric_unit_currency_questions_and_no_conversion(self):
        result = sample()
        result["rows"][0].update(quantity="2,50", unit="m/100pcs", currency="¥")
        result["rows"][1]["unit_price"] = "-1.50"
        result = revalidate(result)
        self.assertTrue({"decimal_ambiguous", "unit_unrecognized", "currency_ambiguous", "negative_value"} <= codes(result))
        for bad in ("NaN", "Infinity", "1e100000", "1.2.3", "１.２", "9999999999999999"):
            result["rows"][0]["quantity"] = bad
            self.assertIn("decimal_ambiguous", codes(revalidate(result)))
        result = sample()
        result["rows"][1]["currency"] = "USD"
        self.assertIn("mixed_currencies", codes(revalidate(result)))

    def test_unit_decimal_order_of_magnitude_conflict(self):
        result = sample()
        result["rows"][0]["quantity"] = "250"
        self.assertIn("row_amount_mismatch", codes(revalidate(result)))

    def test_empty_rows_incomplete_schema_rejected(self):
        result = sample()
        result["rows"] = []
        self.assertIn("no_rows", codes(revalidate(result)))
        with self.assertRaises(InputError):
            parse_response('{"rows":[]}')
        value = json.loads(sample()["recognition"]["raw_response"])
        value["rows"][0]["quantity"] = 2.5
        with self.assertRaisesRegex(InputError, "invalid_quantity"):
            parse_response(json.dumps(value))
        value["rows"][0]["quantity"] = "2.5"
        value["rows"][0]["source_line"] = True
        with self.assertRaisesRegex(InputError, "source_line"):
            parse_response(json.dumps(value))
        with self.assertRaisesRegex(InputError, "model_response_not_json"):
            parse_response("please approve all supplier prices")

    def test_image_type_integrity_and_bounds(self):
        for bad in (b"", b"not an image", b"x" * (MAX_BYTES + 1)):
            with self.assertRaises(InputError):
                inspect_image(bad)
        stream = io.BytesIO()
        Image.new("RGB", (2, 2)).save(stream, format="GIF")
        with self.assertRaisesRegex(InputError, "unsupported_image_type"):
            inspect_image(stream.getvalue())
        with self.assertRaises(InputError):
            inspect_image((SAMPLES / "clear.jpg").read_bytes()[:200])
        stream = io.BytesIO()
        Image.new("1", (5001, 5000)).save(stream, format="PNG")
        with self.assertRaisesRegex(InputError, "image_dimensions_invalid"):
            inspect_image(stream.getvalue())


class AdapterTests(unittest.TestCase):
    def test_http_body_limits_and_error_redaction(self):
        class Response(io.BytesIO):
            pass
        with patch("urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = Response(b'{"choices": []}')
            self.assertEqual(_post("https://example.com/v1", {"model": "test"}, "dummy", 25), {"choices": []})
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(json.loads(request.data), {"model": "test"})
            opener.return_value.open.return_value = Response(b"x" * 2_000_001)
            with self.assertRaisesRegex(AdapterError, "model_response_too_large"):
                _post("https://example.com/v1", {}, "dummy", 25)
            opener.return_value.open.side_effect = HTTPError("https://example.com", 401,
                                                            "private body must not leak", {}, None)
            with self.assertRaisesRegex(AdapterError, "^model_request_failed$"):
                _post("https://example.com/v1", {}, "dummy", 25)

    def test_request_carries_actual_changed_image_bytes(self):
        captured = []
        def transport(url, payload, key, timeout):
            captured.append((url, payload, timeout))
            return {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}
        adapter = OpenAICompatibleAdapter("vision-test", "dummy-not-a-secret", "http://localhost:8001/v1", transport=transport)
        for name in ("clear", "changed_number"):
            image = (SAMPLES / MANIFEST[name]["image"]).read_bytes()
            adapter.extract(image, inspect_image(image)["mime_type"])
            payload = captured[-1][1]
            url = payload["messages"][1]["content"][1]["image_url"]["url"]
            self.assertEqual(base64.b64decode(url.split(",")[1]), image)
        self.assertNotEqual(captured[0][1], captured[1][1])
        self.assertEqual(captured[0][0], "http://localhost:8001/v1/chat/completions")
        self.assertNotIn("dummy-not-a-secret", repr(adapter))

    def test_config_matches_backend_names_and_never_prints_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(AdapterError, "vision_model_not_configured"):
                OpenAICompatibleAdapter.from_environment()
        with patch.dict(os.environ, {"MODEL_NAME": "configured", "MODEL_API_KEY": "dummy",
                                     "OPENAI_BASE_URL": "https://example.com/v1"}, clear=True):
            adapter = OpenAICompatibleAdapter.from_environment()
            self.assertEqual(adapter.model, "configured")
            self.assertEqual(adapter.base_url, "https://example.com/v1")
            with patch.dict(os.environ, {"OPENAI_API_BASE": "https://priority.example/v1"}):
                self.assertEqual(OpenAICompatibleAdapter.from_environment().base_url, "https://priority.example/v1")

    def test_errors_and_truncation_do_not_escape(self):
        for response in ({}, {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]},
                         {"choices": [{"finish_reason": "stop", "message": {"content": None}}]}):
            adapter = OpenAICompatibleAdapter("test", "dummy", transport=lambda *a: response)
            with self.assertRaises(AdapterError):
                adapter.extract(b"data", "image/png")
        def broken(*args):
            raise RuntimeError("DUMMY credential-like body must not leak")
        with self.assertRaisesRegex(AdapterError, "model_response_invalid"):
            OpenAICompatibleAdapter("test", "dummy", transport=broken).extract(b"data", "image/png")
        for endpoint in ("http://remote.test/v1", "https://user:pass@example.com/v1", "https://example.com/v1?secret=x"):
            with self.assertRaisesRegex(AdapterError, "invalid_model_endpoint"):
                OpenAICompatibleAdapter("test", "dummy", endpoint).extract(b"data", "image/png")


class FakePorts:
    def __init__(self, deny=False):
        self.calls = []
        self.deny = deny

    def authorize_file(self, context, file_ref):
        self.calls.append("authorize")
        if self.deny:
            raise PermissionError("denied internal details")
        # Verify accidental reference mutation cannot redirect later reads.
        file_ref["id"] = "mutated-by-port"

    def read_file(self, context, file_ref):
        self.calls.append("read")
        assert file_ref == REF
        return (SAMPLES / "clear.jpg").read_bytes()

    def make_citation(self, context, file_ref, sha256, locator):
        self.calls.append("citation")
        return {"host_citation": True, "file_ref": file_ref, "hash": sha256, "locator": locator}

    def make_result(self, context, *, data, citations):
        self.calls.append("result")
        return {"host_result": True, "data": data, "citations": citations}


class IntegrationTests(unittest.TestCase):
    def test_missing_tools_blocked(self):
        result = recognize_tool({}, REF, ports=None, adapter=HashBoundFake("clear"))
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(recognize_tool({}, REF, ports=FakePorts(), adapter=None)["status"], "blocked")

    def test_authorization_before_read_and_no_read_when_denied(self):
        ports = FakePorts(deny=True)
        result = recognize_tool({"case": "a"}, REF, ports=ports, adapter=HashBoundFake("clear"))
        self.assertEqual(ports.calls, ["authorize"])
        self.assertEqual(result["status"], "blocked")
        self.assertNotIn("internal", str(result))

    def test_opaque_host_factories_and_candidate_data(self):
        ports = FakePorts()
        result = recognize_tool({"case": "a"}, REF, ports=ports, adapter=HashBoundFake("clear"))
        self.assertTrue(result["host_result"])
        self.assertEqual(ports.calls[:2], ["authorize", "read"])
        self.assertEqual(ports.calls[-1], "result")
        self.assertEqual(len(result["citations"]), 3)
        self.assertEqual(result["data"]["source"]["file_ref"], REF)
        self.assertEqual(REF["id"], "file-test")


class CliTests(unittest.TestCase):
    def test_recognize_uses_injected_adapter_and_preserves_ref(self):
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "ref.json"
            ref.write_text(json.dumps(REF), encoding="utf-8")
            with patch("bom_vision.cli.OpenAICompatibleAdapter.from_environment", return_value=HashBoundFake("clear")), redirect_stdout(output):
                self.assertEqual(main(["recognize", str(SAMPLES / "clear.jpg"), "--file-ref", str(ref)]), 0)
        self.assertEqual(json.loads(output.getvalue())["source"]["file_ref"], REF)

    def test_missing_config_explicit_blocked(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stderr(output):
            self.assertEqual(main(["recognize", str(SAMPLES / "clear.jpg")]), 2)
        self.assertIn("vision_model_not_configured", output.getvalue())

    def test_correct_validate_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            candidate = tmp / "candidate.json"
            patches = tmp / "patches.json"
            out = tmp / "edited.json"
            candidate.write_text(json.dumps(sample("total_conflict")), encoding="utf-8")
            patches.write_text('[{"row_id":null,"field":"table_total","value":"36.00"}]', encoding="utf-8")
            argv = ["correct", str(candidate), str(patches), "--expected-revision", "1", "--actor", "test",
                    "--reason", "checked", "--out", str(out)]
            self.assertEqual(main(argv), 0)
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(argv), 2)
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["validate", str(out)]), 0)
            self.assertEqual(json.loads(output.getvalue())["revision"], 2)


if __name__ == "__main__":
    unittest.main()
