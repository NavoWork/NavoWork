"""One behavioral contract for local adapter and a host DTO/service substitute."""
from pathlib import Path
import pytest
from navowork_agent.adapters.local import LocalAdapter
from navowork_agent.contracts import ExecutionContext, ToolResult, AgentError, FileRef
from navowork_agent.ports import CaseContextPort, FileStorePort, ArtifactPort, EventSink


class HostServiceDouble:
    """Host facade substitute with camelCase blob DTOs, not a real backend integration."""
    def __init__(self, root, context):
        self.storage = LocalAdapter(root, context)

    def context(self): return self.storage.context()
    def user_facts(self): return self.storage.user_facts()
    def assert_current(self): return self.storage.assert_current()
    def list_files(self):
        dtos = [{"blobId": f.file_id, "caseId": f.case_id, "sha256": f.sha256,
                 "filename": f.name, "mediaType": f.media_type, "byteSize": f.byte_size, "role": f.role}
                for f in self.storage.list_files()]
        return [FileRef(file_id=d["blobId"], case_id=d["caseId"], sha256=d["sha256"], name=d["filename"],
                        media_type=d["mediaType"], byte_size=d["byteSize"], role=d["role"]) for d in dtos]
    def read_bytes(self, file_id): return self.storage.read_bytes(file_id)
    def read_document(self, file_id): return self.storage.read_document(file_id)
    def list_artifacts(self): return self.storage.list_artifacts()
    def get_artifact(self, artifact_id, version=None): return self.storage.get_artifact(artifact_id, version)
    def list_exports(self, artifact_id, version): return self.storage.list_exports(artifact_id, version)
    def execute_once(self, key, payload, operation, *, write=True):
        return self.storage.execute_once(key, payload, operation, write=write)
    def emit(self, kind, summary, result_ref=None): return self.storage.emit(kind, summary, result_ref)
    def import_source(self, path): return self.storage.import_source(path)


@pytest.fixture(params=[LocalAdapter, HostServiceDouble])
def port(request, tmp_path):
    return request.param(tmp_path / "workspace", ExecutionContext(case_id="case_a", job_id="job", run_id="run"))


def test_scope_integrity_and_protocols(port, tmp_path):
    assert all(isinstance(port, p) for p in (CaseContextPort, FileStorePort, ArtifactPort, EventSink))
    source = tmp_path / "source.txt"
    source.write_text("actual content", encoding="utf-8")
    ref = port.import_source(source)
    assert port.list_files() == [ref]
    assert port.read_bytes(ref.file_id) == b"actual content"
    assert port.read_document(ref.file_id)["sections"][0]["text"] == "actual content"
    with pytest.raises(AgentError, match="unavailable"):
        port.read_bytes("foreign-case-file")
    assert port.list_artifacts() == []


def test_idempotency_and_result_event_contract(port):
    calls = []
    def op(state):
        calls.append(True)
        return ToolResult(status="needs_info", data={"value": 1})
    first = port.execute_once("key", {"name": "probe", "value": 1}, op)
    assert port.execute_once("key", {"name": "probe", "value": 1}, op) == first
    assert calls == [True]
    with pytest.raises(AgentError) as exc:
        port.execute_once("key", {"name": "probe", "value": 2}, op)
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"
    event = port.emit("probe", "Public summary")
    assert event.seq == 2 and event.run_id == "run"


def test_same_tool_service_runs_against_host_substitute(port):
    from support import base_snapshot, publish
    from navowork_agent.tools.service import ToolService
    storage = port.storage if isinstance(port, HostServiceDouble) else port
    storage.update_user_facts({"fx": "7.20", "margin": "0.20"}, supersede=False)
    snapshot = base_snapshot(port)
    result = publish(ToolService(port), snapshot)
    assert len(result.outputs) == 4 and result.status == "needs_review", result
    assert all(port.read_bytes(f.file_id) for f in result.outputs)


def test_read_only_and_stale_context(tmp_path):
    root = tmp_path / "workspace"
    c = ExecutionContext(case_id="c", job_id="j", run_id="r")
    a = LocalAdapter(root, c)
    file = tmp_path / "source.txt"
    file.write_text("hello")
    ref = a.import_source(file)
    reader = LocalAdapter(root, c.model_copy(update={"can_write": False}))
    assert reader.read_bytes(ref.file_id) == b"hello"
    assert reader.execute_once("read", {"name": "read"}, lambda _: ToolResult(status="success"), write=False).status == "success"
    with pytest.raises(AgentError): reader.import_source(file)
    a.update_user_facts({"new": "fact"})
    with pytest.raises(AgentError) as exc: reader.assert_current()
    assert exc.value.code == "WRITE_DENIED"
