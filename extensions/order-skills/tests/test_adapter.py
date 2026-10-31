"""Interface substitutes only. These classes are NOT shared-contract proposals."""

from dataclasses import dataclass
import hashlib
import json
import unittest

from order_skills.adapter import (DRAFT_CAPABILITIES, READ_CAPABILITIES,
                                 HostBlocked, StaleVersion, evidence_in, run)
from support import CASE, order, sample


@dataclass
class FakeExecutionContext:
    case_id: str = CASE
    can_read: bool = True
    can_draft: bool = True
    idempotency_key: str = "fake-run-1"


@dataclass
class FakeCitation:
    source_id: str
    locator: str


@dataclass
class FakeFileRef:
    id: str
    state: str = "draft"


@dataclass
class FakeToolResult:
    status: str
    data: dict
    citations: list
    files: list
    blockers: list


class FakeHost:
    def __init__(self):
        self.available = set(READ_CAPABILITIES | DRAFT_CAPABILITIES)
        self.events = []
        self.stale = False
        self.bad_source = False
        self.renderer_blocked = False
        self.empty_files = False
        self.writes = {}

    def authorize(self, context, operation, case_id, *, draft):
        self.events.append("authorize")
        return context.can_read and context.case_id == case_id and (not draft or context.can_draft)

    def capabilities(self, context):
        self.events.append("capabilities")
        return self.available

    def validate_references(self, context, request):
        self.events.append("validate_references")
        if self.stale:
            raise StaleVersion()
        if self.bad_source or any(e["case_id"] != context.case_id for e in evidence_in(request)):
            raise PermissionError()
        # Real integration must also load records and validate locator text, role,
        # scope, versions and current hashes. This offline substitute does not.

    def citation(self, context, evidence):
        self.events.append("citation")
        return FakeCitation(evidence["source_id"], evidence["locator"])

    def create_document_draft(self, context, *, operation, data, citations):
        self.events.append("create_document_draft")
        if self.renderer_blocked:
            raise HostBlocked()
        if self.empty_files:
            return []
        digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        key = (context.idempotency_key, digest)
        self.writes.setdefault(key, FakeFileRef(f"fake-file-{len(self.writes)}"))
        return [self.writes[key]]

    def result(self, context, **kwargs):
        return FakeToolResult(**kwargs)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.host = FakeHost()
        self.context = FakeExecutionContext()

    def test_reuses_host_result_citation_and_file_types(self):
        result = run("pi_prepare", order(), self.context, self.host, create_file=True)
        self.assertIsInstance(result, FakeToolResult)
        self.assertIsInstance(result.files[0], FakeFileRef)
        self.assertIsInstance(result.citations[0], FakeCitation)
        self.assertEqual(result.data["status"], "draft")
        self.assertEqual(self.host.events[:3], ["authorize", "capabilities", "validate_references"])
        self.assertEqual(self.host.events[-1], "create_document_draft")

    def test_each_missing_capability_blocks_before_reference_reads(self):
        for capability in READ_CAPABILITIES | DRAFT_CAPABILITIES:
            host = FakeHost()
            host.available.remove(capability)
            result = run("pi_prepare", order(), self.context, host, create_file=True)
            self.assertEqual(result.status, "blocked")
            self.assertEqual(result.blockers[0]["capabilities"], [capability])
            self.assertNotIn("validate_references", host.events)

    def test_analysis_without_renderer(self):
        self.host.available = set(READ_CAPABILITIES)
        result = run("po_check", order(), self.context, self.host)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.files, [])
        self.assertNotIn("create_document_draft", self.host.events)

    def test_case_denial_is_redacted_before_any_reads(self):
        self.context.case_id = "OTHER"
        result = run("pi_prepare", order(), self.context, self.host, create_file=True)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.data, {})
        self.assertEqual(result.citations, [])
        self.assertEqual(self.host.events, ["authorize"])

    def test_draft_permission_is_host_injected(self):
        self.context.can_draft = False
        result = run("pi_prepare", order(), self.context, self.host, create_file=True)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(self.host.writes, {})

    def test_cross_case_source_denied(self):
        request = sample()
        request["response"]["evidence"]["case_id"] = "OTHER"
        result = run("sample_feedback", request, self.context, self.host)
        self.assertEqual(result.blockers[0]["code"], "SCOPE_DENIED")
        self.assertEqual(result.data, {})

    def test_host_rejects_forged_source(self):
        self.host.bad_source = True
        result = run("po_check", order(), self.context, self.host)
        self.assertEqual(result.status, "blocked")
        self.assertNotIn("citation", self.host.events)

    def test_stale_version_conflicts_before_write(self):
        self.host.stale = True
        result = run("pi_prepare", order(), self.context, self.host, create_file=True)
        self.assertEqual(result.status, "conflict")
        self.assertEqual(result.files, [])
        self.assertEqual(self.host.writes, {})

    def test_renderer_failure_is_blocked_and_keeps_reviewable_data(self):
        self.host.renderer_blocked = True
        result = run("pi_prepare", order(), self.context, self.host, create_file=True)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.data["status"], "draft")
        self.assertEqual(result.files, [])

    def test_no_files_returned_does_not_claim_export(self):
        self.host.empty_files = True
        result = run("pi_prepare", order(), self.context, self.host, create_file=True)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.files, [])

    def test_stub_demonstrates_host_owned_idempotency(self):
        first = run("pi_prepare", order(), self.context, self.host, create_file=True)
        second = run("pi_prepare", order(), self.context, self.host, create_file=True)
        self.assertEqual(first.files, second.files)
        self.assertEqual(len(self.host.writes), 1)

    def test_unknown_operation_and_malformed_request(self):
        for operation, request in (("approve", order()), ("pi_prepare", [])):
            self.assertEqual(run(operation, request, self.context, self.host).status, "error")

    def test_missing_info_and_conditional_statuses(self):
        request = sample()
        del request["response"]
        self.assertEqual(run("sample_feedback", request, self.context, self.host).status, "needs_info")
        self.assertEqual(run("sample_feedback", sample("conditional"), self.context, self.host).status, "needs_review")


if __name__ == "__main__":
    unittest.main()
