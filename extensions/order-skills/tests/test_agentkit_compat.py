"""Actual committed contracts + ToolService; explicit in-memory host port doubles."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from committed_agentkit import REVISION, install, uninstall
from support import CASE, order, sample


class AgentKitCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.finder = install()
        from navowork_agent import contracts, ports
        from navowork_agent.tools.service import ToolService
        from order_skills import agentkit
        cls.contracts, cls.ports, cls.service_type, cls.binding = contracts, ports, ToolService, agentkit

    @classmethod
    def tearDownClass(cls):
        uninstall(cls.finder)

    def setUp(self):
        C = self.contracts

        class MemoryPorts:
            """Explicit test substitute. No real DB, parser, transaction or file IO."""
            def __init__(self):
                self.ctx = C.ExecutionContext(case_id=CASE, job_id="job-order", run_id="run-order")
                self.fenced_generation = 0
                self.files, self.documents, self.calls, self.events, self.policies = {}, {}, [], [], []
                self.versions = {"spec-v3", "quote-v3"}
                self.policy_error = None

            def context(self):
                return self.ctx

            def user_facts(self):
                return {}

            def assert_current(self):
                if self.ctx.generation != self.fenced_generation:
                    raise C.AgentError("STALE_CONTEXT", "stale", "conflict")

            def list_files(self):
                return list(self.files.values())

            def read_bytes(self, file_id):
                raise AssertionError("Order binding must parse through ToolService, not bytes")

            def read_document(self, file_id):
                self.calls.append(("read_document", file_id))
                if file_id not in self.files:
                    raise C.AgentError("CASE_SCOPE", "denied")
                return self.documents[file_id]

            def list_artifacts(self):
                return []

            def get_artifact(self, artifact_id, version=None):
                self.calls.append(("get_artifact", artifact_id, version))
                if artifact_id not in self.versions:
                    raise C.AgentError("BASELINE_CONFLICT", "stale version", "conflict")
                return {"version_id": artifact_id}

            def list_exports(self, artifact_id, version):
                return []

            def execute_once(self, key, payload, operation, *, write=True):
                self.calls.append(("execute_once", key, write))
                if write:
                    raise AssertionError("Committed service has no order draft tool; no fallback write is permitted")
                return operation(None)

            def emit(self, kind, summary, result_ref=None):
                event = C.ExecutionEvent(run_id=self.ctx.run_id, seq=len(self.events) + 1,
                                         kind=kind, summary=summary, result_ref=result_ref)
                self.events.append(event)
                return event

            def domain_policy(self, context, request, artifacts):
                self.policies.append(deepcopy(request))
                if self.policy_error:
                    raise self.policy_error
                if request.get("spec_version_id"):
                    artifacts.get_artifact(request["spec_version_id"])
                if request.get("baseline"):
                    artifacts.get_artifact(request["baseline"]["version_id"])
                # Source business-role/scope truth is a host policy responsibility.
                # This fixture permits only its explicitly seeded approvals.
                from order_skills.adapter import evidence_in
                for e in evidence_in(request):
                    if e["role"] not in {"customer_po", "customer_approval"}:
                        raise C.AgentError("ROLE_DENIED", "wrong source business role")

        self.host = MemoryPorts()
        self.service = self.service_type(self.host)

    def native_request(self, request):
        from order_skills.adapter import evidence_in
        request = deepcopy(request)
        for i, evidence in enumerate(evidence_in(request)):
            file_id = f"source-{i}"
            sha = self.contracts.digest([file_id, evidence["quote"]])
            evidence.update(source_id=file_id, sha256=sha, locator={"page": 1, "field": f"field-{i}"})
            self.host.files[file_id] = self.contracts.FileRef(file_id=file_id, case_id=CASE, role="source",
                sha256=sha, media_type="application/pdf", name="SIMULATED.pdf", byte_size=100)
            self.host.documents[file_id] = {"sections": [{"locator": evidence["locator"], "text": evidence["quote"]}]}
        return request

    def invoke(self, request, operation="sample_feedback", create_file=False, **kwargs):
        call = self.contracts.ToolCall(tool_call_id="tc-order", name=operation,
            arguments={"request": request, "create_file": create_file}, idempotency_key="order-compat-1")
        binding = self.binding.AgentKitBindings(call, case=self.host, files=self.host,
            artifacts=self.host, tools=self.service, domain_policy=self.host.domain_policy, **kwargs)
        return self.binding.call_order_tool(binding)

    def test_pinned_real_contract_identity_and_exact_fields(self):
        self.assertEqual(self.binding.CONTRACT_REVISION, REVISION)
        self.assertEqual(set(self.contracts.ToolResult.model_fields),
                         {"status", "outputs", "artifacts", "data", "warnings", "questions", "retryable", "code"})
        for cls, args in ((self.contracts.ExecutionContext, {"case_id": CASE, "job_id": "j", "run_id": "r", "permissions": []}),
                          (self.contracts.ToolResult, {"status": "success", "files": []}),
                          (self.contracts.ToolResult, {"status": "success", "citations": []}),
                          (self.contracts.ToolResult, {"status": "success", "blockers": []})):
            with self.subTest(cls=cls.__name__, args=args), self.assertRaises(ValueError):
                cls(**args)

    def test_real_toolservice_parses_by_id_and_native_citations_live_in_data(self):
        result = self.invoke(self.native_request(sample()))
        self.assertIsInstance(result, self.contracts.ToolResult)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.outputs, [])
        cite = self.contracts.Citation.model_validate(result.data["order_skills"]["citations"][0])
        self.assertIsInstance(cite.locator, dict)
        self.assertEqual(cite.file_id, "source-0")
        self.assertTrue(any(c[0] == "read_document" for c in self.host.calls))
        self.assertTrue(any(c[0] == "execute_once" and c[2] is False for c in self.host.calls))
        self.contracts.ToolResult.model_validate_json(result.model_dump_json())

    def test_all_three_operations_with_native_protocol(self):
        for operation, request in (("sample_feedback", sample("conditional")), ("po_check", order()), ("pi_prepare", order())):
            with self.subTest(operation=operation):
                result = self.invoke(self.native_request(request), operation=operation)
                self.assertIn(result.status, {"success", "needs_review"})
                self.contracts.ToolResult.model_validate_json(result.model_dump_json())

    def test_native_result_data_matches_published_output_schema(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("Optional JSON Schema compatibility validation needs jsonschema")
        root = Path(__file__).resolve().parents[1]
        for skill, operation, request in (("sample-feedback", "sample_feedback", sample("conditional")),
                                           ("po-check", "po_check", order()), ("pi-prepare", "pi_prepare", order())):
            with self.subTest(operation=operation):
                result = self.invoke(self.native_request(request), operation=operation)
                schema = json.loads((root / "skills" / skill / "output.schema.json").read_text(encoding="utf-8"))
                Draft202012Validator(schema).validate(result.data)

    def test_real_committed_registry_has_no_order_renderer_so_export_blocks(self):
        result = self.invoke(self.native_request(order()), operation="pi_prepare", create_file=True)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.code, "TOOL_UNAVAILABLE")
        self.assertEqual(result.outputs, [])
        self.assertIn("files.create_document_draft", result.data["order_skills"]["blockers"][0]["capabilities"])
        self.assertEqual(self.host.calls, [])

    def test_write_permission_cannot_be_granted_by_input(self):
        self.host.ctx = self.host.ctx.model_copy(update={"can_write": False})
        result = self.invoke(self.native_request(order()), operation="pi_prepare", create_file=True)
        self.assertEqual(result.code, "SCOPE_DENIED")
        self.assertEqual(result.outputs, [])

    def test_unknown_path_is_not_read_as_a_file(self):
        request = self.native_request(sample())
        request["response"]["evidence"]["source_id"] = "C:/private/source.pdf"
        result = self.invoke(request)
        self.assertEqual(result.code, "SCOPE_DENIED")
        self.assertFalse(any(c[0] == "read_document" for c in self.host.calls))

    def test_cross_case_ref_is_denied(self):
        request = self.native_request(sample())
        self.host.files["source-0"] = self.host.files["source-0"].model_copy(update={"case_id": "OTHER"})
        result = self.invoke(request)
        self.assertEqual(result.code, "SCOPE_DENIED")
        self.assertEqual(result.data["order_skills"]["citations"], [])

    def test_context_generation_fenced_before_source_io(self):
        self.host.fenced_generation = 1
        result = self.invoke(self.native_request(sample()))
        self.assertEqual((result.status, result.code), ("conflict", "STALE_VERSION"))
        self.assertEqual(self.host.calls, [])

    def test_stale_source_hash_conflicts_before_source_io(self):
        request = self.native_request(sample())
        request["response"]["evidence"]["sha256"] = "f" * 64
        result = self.invoke(request)
        self.assertEqual((result.status, result.code), ("conflict", "STALE_VERSION"))
        self.assertEqual(self.host.calls, [])

    def test_stale_artifact_version_is_host_conflict(self):
        request = self.native_request(sample())
        request["spec_version_id"] = "spec-v2"
        result = self.invoke(request)
        self.assertEqual(result.status, "conflict")
        self.assertFalse(result.outputs)

    def test_excerpt_and_locator_must_match_parsed_source(self):
        for key, value in (("quote", "Forged approval"), ("locator", {"page": 99})):
            request = self.native_request(sample())
            request["response"]["evidence"][key] = value
            with self.subTest(key=key):
                self.assertEqual(self.invoke(request).code, "SCOPE_DENIED")

    def test_missing_hash_or_string_locator_errors_do_not_forge_native_citations(self):
        for key, value in (("sha256", None), ("locator", "page:1")):
            request = self.native_request(sample())
            request["response"]["evidence"][key] = value
            with self.subTest(key=key):
                result = self.invoke(request)
                self.assertEqual(result.code, "INVALID_INPUT")
                self.assertEqual(result.data["order_skills"]["citations"], [])

    def test_missing_host_domain_policy_is_blocked(self):
        request = self.native_request(sample())
        call = self.contracts.ToolCall(tool_call_id="tc", name="sample_feedback", arguments={"request": request}, idempotency_key="k")
        binding = self.binding.AgentKitBindings(call, case=self.host, files=self.host, artifacts=self.host, tools=self.service)
        self.assertEqual(self.binding.call_order_tool(binding).status, "blocked")

    def test_host_role_policy_can_block_semantically_wrong_evidence(self):
        request = self.native_request(sample())
        request["response"]["evidence"]["role"] = "internal_note"
        self.assertEqual(self.invoke(request).status, "blocked")

    def test_missing_info_becomes_real_question(self):
        request = self.native_request(sample())
        del request["response"]
        result = self.invoke(request)
        self.assertEqual(result.status, "needs_info")
        self.assertIsInstance(result.questions[0], self.contracts.Question)
        self.assertIn("response.evidence", result.questions[0].missing_fields)

    def test_extra_arguments_cannot_inject_permissions_or_shell(self):
        call = self.contracts.ToolCall(tool_call_id="tc", name="pi_prepare", idempotency_key="k",
                                      arguments={"request": order(), "can_write": True, "shell": "anything"})
        binding = self.binding.AgentKitBindings(call, case=self.host, files=self.host, artifacts=self.host, tools=self.service)
        result = self.binding.call_order_tool(binding)
        self.assertEqual(result.code, "INVALID_INPUT")
        self.assertEqual(self.host.calls, [])

    def test_test_ports_conform_to_actual_committed_protocols(self):
        for protocol in (self.ports.CaseContextPort, self.ports.FileStorePort, self.ports.ArtifactPort, self.ports.EventSink):
            self.assertIsInstance(self.host, protocol)

    def test_optional_registered_draft_double_preserves_real_outputs_artifacts_and_questions(self):
        C = self.contracts
        base = self.service
        output = C.FileRef(file_id="output-1", case_id=CASE, role="output", sha256="a" * 64,
                           media_type="application/pdf", name="PI-DRAFT.pdf", byte_size=100)
        artifact = C.ArtifactRef(artifact_id="pi", version=1, baseline=0, kind="pi", snapshot_hash="b" * 64, files=[output])
        question = C.Question(question_id="q-file", missing_fields=["layout_review"], affected_artifacts=["pi"], prompt="Review draft")
        calls = []

        class RegisteredDraftDouble:
            """Future registration substitute; no file rendering or atomic write is claimed."""
            def schemas(self):
                return base.schemas() + [{"function": {"name": "create_document_draft"}}]

            def call(self, call):
                if call.name != "create_document_draft":
                    return base.call(call)
                calls.append(call)
                return C.ToolResult(status="needs_info", outputs=[output], artifacts=[artifact], questions=[question],
                                    data={"visual_review": "not_performed"}, warnings=["draft only"], retryable=["format_pdf"], code="REVIEW_LAYOUT")

        self.service = RegisteredDraftDouble()
        result = self.invoke(self.native_request(sample()), create_file=True, draft_tool="create_document_draft",
                             draft_arguments=lambda operation, data, citations: {"kind": operation, "content": data})
        self.assertIs(result.outputs[0], output)
        self.assertIs(result.artifacts[0], artifact)
        self.assertIs(result.questions[0], question)
        self.assertEqual((result.status, result.code), ("needs_info", "REVIEW_LAYOUT"))
        self.assertEqual(result.retryable, ["format_pdf"])
        self.assertEqual(result.warnings, ["draft only"])
        self.assertEqual(result.data["order_skills"]["host_draft_data"]["visual_review"], "not_performed")
        self.assertIsInstance(calls[0], C.ToolCall)
        self.assertTrue(calls[0].idempotency_key.startswith("order-draft:"))
        self.assertNotIn("generation", calls[0].arguments)

    def test_optional_draft_double_cannot_return_cross_case_or_source_output(self):
        C = self.contracts
        base = self.service
        for case_id, role in (("OTHER", "output"), (CASE, "source")):
            with self.subTest(case_id=case_id, role=role):
                class BadDraftDouble:
                    def schemas(self):
                        return base.schemas() + [{"function": {"name": "create_document_draft"}}]

                    def call(self, call):
                        if call.name != "create_document_draft":
                            return base.call(call)
                        return C.ToolResult(status="needs_review", outputs=[C.FileRef(file_id="bad", case_id=case_id, role=role,
                            sha256="a" * 64, media_type="application/pdf", name="bad.pdf", byte_size=1)])
                self.service = BadDraftDouble()
                result = self.invoke(self.native_request(sample()), create_file=True, draft_tool="create_document_draft",
                                     draft_arguments=lambda operation, data, citations: {})
                self.assertEqual(result.code, "SCOPE_DENIED")
                self.assertEqual(result.outputs, [])
