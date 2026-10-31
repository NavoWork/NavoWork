"""Thin host boundary. Generic parameters are the HOST's existing contract types.

No substitute ExecutionContext/FileRef/Citation/ToolResult is shipped here. The
uncommitted agent-kit ABI is deliberately not imported or inferred.
"""

from copy import deepcopy
from typing import Protocol, TypeVar

from .domain import InvalidInput, compare_po, prepare_pi, review_sample

ExecutionContext = TypeVar("ExecutionContext", contravariant=True)
FileRef = TypeVar("FileRef")
Citation = TypeVar("Citation")
ToolResult = TypeVar("ToolResult", covariant=True)

OPERATIONS = {"sample_feedback": review_sample, "po_check": compare_po, "pi_prepare": prepare_pi}
READ_CAPABILITIES = frozenset({"case.read", "sources.read", "artifacts.read_version"})
DRAFT_CAPABILITIES = frozenset({"artifacts.create_draft", "files.create_document_draft"})


class HostBlocked(RuntimeError):
    """Host reports an unavailable tool or unsatisfied policy requirement."""


class StaleVersion(RuntimeError):
    """Host found a changed, revoked or superseded input version."""


class HostBindings(Protocol[ExecutionContext, FileRef, Citation, ToolResult]):
    """Integration port, NOT a proposed replacement for shared contracts.

    Implement these methods in the host's integration module. Authorize must
    check actor/Case permissions. validate_references must resolve ALL supplied
    source IDs, evidence roles, locators/quotes, sample/quote/spec versions and
    scope bindings against host records, not accept model assertions as grants.
    It must reject stale versions. Exceptions are translated fail-closed below.
    """

    def capabilities(self, context: ExecutionContext) -> set[str]: ...
    def authorize(self, context: ExecutionContext, operation: str, case_id: str, *, draft: bool) -> bool: ...
    def validate_references(self, context: ExecutionContext, request: dict) -> None: ...
    def citation(self, context: ExecutionContext, evidence: dict) -> Citation: ...
    def create_document_draft(self, context: ExecutionContext, *, operation: str,
                              data: dict, citations: list[Citation]) -> list[FileRef]:
        """Use generic file tools, preserve draft labels/conflicts, enforce
        idempotency/base versions from ExecutionContext and return HOST FileRefs.
        Missing renderer/format support must raise HostBlocked. Never publish.
        """
        ...
    def result(self, context: ExecutionContext, *, status: str, data: dict,
               citations: list[Citation], files: list[FileRef], blockers: list[dict]) -> ToolResult: ...


def evidence_in(value):
    """Collect located candidate evidence; host still validates each reference."""
    if isinstance(value, dict):
        if all(isinstance(value.get(k), str) and value[k].strip()
               for k in ("source_id", "locator", "quote", "role", "case_id")):
            yield value
        for item in value.values():
            yield from evidence_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from evidence_in(item)


def run(operation: str, request: dict, context: ExecutionContext,
        host: HostBindings[ExecutionContext, FileRef, Citation, ToolResult], *,
        create_file: bool = False) -> ToolResult:
    """Return a host ToolResult; module-specific fields live only in its data."""
    data, citations, files = {}, [], []
    try:
        if operation not in OPERATIONS:
            raise InvalidInput("Unknown operation")
        if not isinstance(request, dict):
            raise InvalidInput("Request must be an object")
        request = deepcopy(request)
        case_id = request.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise InvalidInput("case_id is required")
        # Check permission before reading capabilities or resolving any source.
        if not host.authorize(context, operation, case_id, draft=create_file):
            raise PermissionError("Case permission denied")
        required = READ_CAPABILITIES | (DRAFT_CAPABILITIES if create_file else set())
        missing = sorted(required - host.capabilities(context))
        if missing:
            return host.result(context, status="blocked", data={}, citations=[], files=[],
                               blockers=[{"code": "TOOL_UNAVAILABLE", "capabilities": missing}])
        host.validate_references(context, request)
        data = OPERATIONS[operation](request)
        seen = set()
        for evidence in evidence_in(request):
            key = tuple(evidence[k] for k in ("case_id", "source_id", "locator", "quote", "role"))
            if key not in seen:
                citations.append(host.citation(context, evidence))
                seen.add(key)
        findings = data.get("findings", [])
        # A complete analysis may still require review; never convert it to approval.
        status = "needs_review" if findings or operation == "pi_prepare" else "success"
        if any(f["code"] in {"FIELD_MISSING", "FIELD_EVIDENCE_MISSING", "FEEDBACK_EVIDENCE_MISSING", "RESPONSE_EVIDENCE_MISSING", "LINES_MISSING"} for f in findings):
            status = "needs_info"
        if create_file:
            files = host.create_document_draft(context, operation=operation, data=data, citations=citations)
            if not files:
                raise HostBlocked("Generic file tool returned no FileRef")
        return host.result(context, status=status, data=data, citations=citations,
                           files=files, blockers=[f for f in findings if f["severity"] == "block"])
    except PermissionError:
        return host.result(context, status="blocked", data={}, citations=[], files=[],
                           blockers=[{"code": "SCOPE_DENIED"}])
    except StaleVersion:
        return host.result(context, status="conflict", data={}, citations=[], files=[],
                           blockers=[{"code": "STALE_VERSION"}])
    except HostBlocked:
        return host.result(context, status="blocked", data=data, citations=citations, files=[],
                           blockers=[{"code": "HOST_TOOL_BLOCKED"}])
    except InvalidInput as error:
        return host.result(context, status="error", data={}, citations=[], files=[],
                           blockers=[{"code": "INVALID_INPUT", "message": str(error)}])
