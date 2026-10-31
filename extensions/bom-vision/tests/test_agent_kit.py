"""Optional tests against actual committed contracts, never local lookalike models.

scripts.check_agent_kit materializes just the committed contract package into a
temporary directory. Normal independent tests skip these if agent-kit is absent.
"""
import hashlib
import unittest
from pathlib import Path

from bom_vision.integration import recognize_tool
from bom_vision.mock import mock_recognize
from demo_mock import Catalog, fingerprint

try:
    from navowork_agent.contracts import Citation, ExecutionContext, FileRef, ToolResult, digest
    AVAILABLE = True
except ImportError:
    AVAILABLE = False

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(AVAILABLE, "run python -m scripts.check_agent_kit --revision d23ab0a")
class AgentKitCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.image = (ROOT / "samples/clear.jpg").read_bytes()
        self.context = ExecutionContext(case_id="demo-case", job_id="demo-job", run_id="demo-run")
        self.ref = FileRef(file_id="demo-image", case_id=self.context.case_id, role="source",
                           sha256=hashlib.sha256(self.image).hexdigest(), media_type="image/jpeg",
                           name="clear.jpg", byte_size=len(self.image))

    def test_mock_candidates_fit_data_without_new_top_level_protocol_fields(self):
        candidate = mock_recognize(self.image, self.ref.model_dump(mode="json"),
                                   catalog=Catalog.load(ROOT / "samples/mock.catalog.json"))
        row = candidate["rows"][0]
        citation = Citation(file_id=self.ref.file_id, sha256=self.ref.sha256,
                            locator=row["source"], excerpt=row["source"]["raw_text"])
        result = ToolResult(status="needs_review", data={"candidate": candidate, "citations": [citation.model_dump(mode="json")]})
        self.assertEqual(result.data["candidate"]["source"]["file_ref"], self.ref.model_dump(mode="json"))
        self.assertEqual(result.data["candidate"]["mode"], "mock")
        self.assertEqual(result.outputs, [])
        self.assertEqual(result.artifacts, [])
        self.assertNotIn("citations", ToolResult.model_fields)
        self.assertEqual(ToolResult.model_validate_json(result.model_dump_json()), result)

    def test_generic_json_fingerprint_matches_committed_canonical_digest(self):
        value = {"workflow": "demo", "rows": ["材料", "3.50"], "approved": False}
        self.assertEqual(fingerprint(value)["sha256"], digest(value))

    def test_existing_seam_can_use_committed_factories_with_host_authorization(self):
        image, expected_ref = self.image, self.ref
        calls = []

        class Ports:
            def authorize_file(self, context, ref):
                calls.append("authorize")
                actual = FileRef.model_validate(ref)
                if not context.can_read or context.case_id != actual.case_id:
                    raise PermissionError()

            def read_file(self, context, ref):
                calls.append("read")
                if FileRef.model_validate(ref) != expected_ref:
                    raise PermissionError()
                return image

            def make_citation(self, context, ref, sha256, locator):
                return Citation(file_id=ref["file_id"], sha256=sha256, locator=locator,
                                excerpt=locator["raw_text"][:4000])

            def make_result(self, context, *, data, citations):
                return ToolResult(status="needs_review", data={"candidate": data,
                                  "citations": [c.model_dump(mode="json") for c in citations]})

        class Fixture:
            name = "compatibility-fixture-not-vision"

            def extract(self, image, mime_type):
                return (ROOT / "samples/clear.fake.json").read_text(encoding="utf-8")

        result = recognize_tool(self.context, self.ref.model_dump(mode="json"), ports=Ports(), adapter=Fixture())
        self.assertIsInstance(result, ToolResult)
        self.assertEqual(calls, ["authorize", "read"])
        calls.clear()
        denied = recognize_tool(self.context.model_copy(update={"can_read": False}), self.ref.model_dump(mode="json"),
                                ports=Ports(), adapter=Fixture())
        self.assertEqual(denied["status"], "blocked")
        self.assertEqual(calls, ["authorize"])
