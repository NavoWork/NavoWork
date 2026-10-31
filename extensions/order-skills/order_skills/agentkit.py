"""Concrete binding to committed navowork_agent contracts (d23ab0a).

Optional integration module: stdlib-only domain/CLI never import this file.
All source IO goes through injected host ports and ToolService.call, never paths.
"""

from copy import deepcopy
from typing import Callable, Protocol

from navowork_agent.contracts import (
    AgentError, Citation, ExecutionContext, FileRef, Question, ToolCall, ToolResult, digest,
)
from navowork_agent.ports import CaseContextPort, FileStorePort, ArtifactPort

from .adapter import HostBlocked, StaleVersion, evidence_in, run
from .domain import InvalidInput

CONTRACT_REVISION = "d23ab0a9ecba4dffd4ce0aa97bd496bf668aa156"


class ToolCaller(Protocol):
    """The existing ToolService surface, not another runtime/tool registry."""
    def schemas(self) -> list[dict]: ...
    def call(self, call: ToolCall) -> ToolResult: ...


DomainPolicy = Callable[[ExecutionContext, dict, ArtifactPort], None]
DraftArguments = Callable[[str, dict, list[Citation]], dict]


def translate(error: AgentError):
    if error.status == "conflict":
        raise StaleVersion() from error
    if error.code in {"CASE_SCOPE", "WRITE_DENIED", "SOURCE_LOCATION", "SOURCE_VERSION"}:
        raise PermissionError() from error
    raise HostBlocked() from error


class AgentKitBindings:
    """One instance per ToolCall. Real contract types; no DTO duplication.

    domain_policy is HOST code verifying extracted field/response classifications,
    source business roles, sample/scope and current artifact version bindings via
    ArtifactPort. It must raise AgentError,
    PermissionError, StaleVersion or HostBlocked on failure. No default approval
    or role is inferred from input text. Missing policy fails closed.

    A host-registered, draft-only document tool and its argument mapper are
    optional. d23ab0a does not have such a tool for these document kinds.
    """

    def __init__(self, call: ToolCall, *, case: CaseContextPort, files: FileStorePort,
                 artifacts: ArtifactPort, tools: ToolCaller,
                 domain_policy: DomainPolicy | None = None,
                 draft_tool: str | None = None, draft_arguments: DraftArguments | None = None):
        self.call = call
        self.case, self.files, self.artifacts, self.tools = case, files, artifacts, tools
        self.domain_policy = domain_policy
        self.draft_tool, self.draft_arguments = draft_tool, draft_arguments
        self._citations = {}
        self._draft_result = None

    def _current(self, context: ExecutionContext, *, write=False):
        try:
            current = self.case.context()
            if (context.case_id, context.job_id, context.run_id) != (current.case_id, current.job_id, current.run_id):
                raise PermissionError()
            if context.generation != current.generation:
                raise StaleVersion()
            if not context.can_read or not current.can_read or (write and (not context.can_write or not current.can_write)):
                raise PermissionError()
            self.case.assert_current()  # Host lease/generation fence, including reads.
        except AgentError as error:
            translate(error)

    def authorize(self, context: ExecutionContext, operation: str, case_id: str, *, draft: bool) -> bool:
        self._current(context, write=draft)
        return case_id == context.case_id

    def capabilities(self, context: ExecutionContext) -> set[str]:
        names = {schema["function"]["name"] for schema in self.tools.schemas()}
        result = {"case.read", "artifacts.read_version"}
        if "read_document" in names:
            result.add("sources.read")
        if self.draft_tool and self.draft_arguments and self.draft_tool in names:
            result |= {"artifacts.create_draft", "files.create_document_draft"}
        return result

    def validate_references(self, context: ExecutionContext, request: dict) -> None:
        self._current(context)
        if self.domain_policy is None:
            raise HostBlocked("Host domain binding policy is required")
        try:
            refs = {ref.file_id: ref for ref in self.files.list_files()}
            for evidence in evidence_in(request):
                file_id = evidence["source_id"]
                ref = refs.get(file_id)
                if ref is None or ref.case_id != context.case_id or evidence["case_id"] != context.case_id:
                    raise PermissionError()
                if not isinstance(evidence["locator"], dict) or not evidence["locator"]:
                    raise InvalidInput("Agent Kit requires the parsed locator dictionary, not a locator string")
                if not evidence.get("sha256"):
                    raise InvalidInput("Agent Kit source evidence requires its captured sha256")
                if len(evidence["quote"]) > 4000:
                    raise InvalidInput("Citation excerpt exceeds the host's 4000-character limit")
                if evidence["sha256"] != ref.sha256:
                    raise StaleVersion()
                read_call = ToolCall(tool_call_id=self.call.tool_call_id + ":read:" + digest(file_id)[:12],
                                     name="read_document", arguments={"file_id": file_id},
                                     idempotency_key="order-read:" + digest([context.model_dump(), self.call.idempotency_key, file_id, ref.sha256]))
                result = self.tools.call(read_call)
                if result.status != "success":
                    translate(AgentError(result.code or "READ_BLOCKED", "Host source read failed", result.status))
                if not any(section.get("locator") == evidence["locator"] and
                           evidence["quote"] in section.get("text", "")
                           for section in result.data.get("sections", [])):
                    raise PermissionError()
                cite = Citation(file_id=file_id, sha256=ref.sha256,
                                locator=deepcopy(evidence["locator"]), excerpt=evidence["quote"])
                self._citations[digest(evidence)] = cite
            # This callback is host policy, never a callable supplied in model args.
            self.domain_policy(context, deepcopy(request), self.artifacts)
        except AgentError as error:
            translate(error)

    def citation(self, context: ExecutionContext, evidence: dict) -> Citation:
        self._current(context)
        try:
            return self._citations[digest(evidence)]
        except KeyError:
            raise PermissionError() from None

    def create_document_draft(self, context: ExecutionContext, *, operation: str,
                              data: dict, citations: list[Citation]) -> list[FileRef]:
        self._current(context, write=True)
        if not self.draft_tool or not self.draft_arguments:
            raise HostBlocked()
        call = ToolCall(tool_call_id=self.call.tool_call_id + ":draft", name=self.draft_tool,
                        arguments=self.draft_arguments(operation, deepcopy(data), citations),
                        idempotency_key="order-draft:" + digest([context.model_dump(), self.call.idempotency_key]))
        result = self.tools.call(call)  # Atomic execute_once/ArtifactTransaction stays in ToolService.
        if result.status not in {"success", "needs_info", "needs_review"}:
            translate(AgentError(result.code or "DRAFT_BLOCKED", "Host draft tool failed", result.status))
        if any(ref.case_id != context.case_id or ref.role not in {"output", "working"} for ref in result.outputs):
            raise PermissionError()
        self._draft_result = result
        return result.outputs

    def result(self, context: ExecutionContext, *, status: str, data: dict,
               citations: list[Citation], files: list[FileRef], blockers: list[dict]) -> ToolResult:
        payload = deepcopy(data)
        payload["order_skills"] = {"operation": self.call.name, "contract_revision": CONTRACT_REVISION,
                                   "citations": [c.model_dump(mode="json") for c in citations],
                                   "blockers": deepcopy(blockers)}
        missing = sorted({f["path"] for f in data.get("findings", []) if f["code"] in {
            "FIELD_MISSING", "FIELD_EVIDENCE_MISSING", "FEEDBACK_EVIDENCE_MISSING", "RESPONSE_EVIDENCE_MISSING", "LINES_MISSING"}})
        questions = [Question(question_id="q_order_" + digest(missing)[:16], missing_fields=missing,
                              affected_artifacts=[self.call.name], prompt="Please provide located evidence for: " + ", ".join(missing))] if missing else []
        draft = self._draft_result if files else None
        if draft:
            payload["order_skills"]["host_draft_data"] = draft.data
            if draft.status == "needs_info" or (draft.status == "needs_review" and status == "success"):
                status = draft.status
            questions.extend(draft.questions)
        return ToolResult(status=status, outputs=files, data=payload, questions=questions,
                          artifacts=draft.artifacts if draft else [], warnings=draft.warnings if draft else [],
                          retryable=draft.retryable if draft else [], code=blockers[0]["code"] if blockers else (draft.code if draft else None))


def call_order_tool(host: AgentKitBindings) -> ToolResult:
    """Optional registration target; creates no runtime, registry or Worker."""
    context = host.case.context()  # Host-only context. No model can provide permissions.
    args = host.call.arguments
    if (set(args) - {"request", "create_file"} or not isinstance(args.get("request"), dict)
            or type(args.get("create_file", False)) is not bool):
        return host.result(context, status="error", data={}, citations=[], files=[],
                           blockers=[{"code": "INVALID_INPUT"}])
    return run(host.call.name, args["request"], context, host, create_file=args.get("create_file", False))
