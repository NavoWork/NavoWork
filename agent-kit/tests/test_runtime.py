from langchain_core.messages import AIMessage
from navowork_agent.tools.service import ToolService
from navowork_agent.runtime.agent import agent_session
from navowork_agent.adapters.local import LocalAdapter
from support import make_adapter, base_snapshot, change_snapshot, baselines, publish, invoke


class ScriptedModel:
    """Explicitly offline tool-calling test double. Never used by CLI or live tests."""
    def __init__(self, responses): self.responses = iter(responses); self.calls = 0
    def bind_tools(self, schemas):
        assert any(s["function"]["name"] == "read_document" for s in schemas)
        assert any(s["function"]["name"] == "create_working_copy" for s in schemas)
        return self
    def invoke(self, messages):
        self.calls += 1
        return next(self.responses)


def call(name, args=None, id="tc"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args or {}, "id": id, "type": "tool_call"}])


def test_graph_tool_loop_pause_restart_and_resume(tmp_path):
    a = make_adapter(tmp_path)
    snapshot = base_snapshot(a)
    pending = change_snapshot(a, snapshot)
    refs = a.list_files()
    fake = ScriptedModel([
        call("list_context"), call("load_skill", {"name": "prepare-quotation"}, "s"),
        call("read_document", {"file_id": refs[0].file_id}, "read"),
        call("calculate_quote", {"pricing": pending.pricing.model_dump(mode="json")}, "calc"),
        call("publish_documents", {"snapshot": pending.model_dump(mode="json"), "baselines": baselines(a), "intent": "initial"}, "draft"),
    ])
    # Missing calculator inputs do not prevent producing independent specification drafts.
    with agent_session(ToolService(a), fake) as run:
        waiting = run(goal="Prepare sourced quotation; ask for missing pricing.")
    assert waiting["status"] == "needs_info", waiting
    assert len(waiting["outputs"]) == 4 and waiting["live_executed"] is False
    a = LocalAdapter(tmp_path, a.context().model_copy(update={"run_id": "r_restart"}))
    priced = change_snapshot(a, snapshot, priced=True)
    a.update_user_facts({"supplement": "Price email supplied"})
    fake = ScriptedModel([call("publish_documents", {"snapshot": priced.model_dump(mode="json"),
        "baselines": baselines(a), "intent": "confirmed_change"}, "write"), AIMessage(content="All files sent and approved")])
    with agent_session(ToolService(a), fake) as run:
        done = run(resume={"text": "Supplier price email is now available"})
    assert len(done["outputs"]) == 8, done
    assert "approved" not in done["summary"]
    assert done["artifacts"][-1]["version"] == 2
    # A completed checkpoint can be inspected after another process/session restart without repeating writes.
    with agent_session(ToolService(a), ScriptedModel([])) as run:
        stable = run()
    assert stable["outputs"] == done["outputs"]
    assert len(a.list_artifacts()) == 3


def test_hypothesis_and_negation_do_not_write(tmp_path):
    a = make_adapter(tmp_path)
    base_snapshot(a)
    for intent in ("如果换彩盒会怎样", "不要修改包装"):
        fake = ScriptedModel([call("list_context"), AIMessage(content="Analysis only. No change applied.")])
        with agent_session(ToolService(a), fake) as run:
            result = run(goal=intent)
        assert not result["outputs"] and not a.list_artifacts()


def test_tool_budget_and_missing_model(tmp_path, monkeypatch):
    a = make_adapter(tmp_path)
    fake = ScriptedModel([call("list_context")])
    with agent_session(ToolService(a), fake, max_tools=1) as run:
        result = run(goal="Inspect")
    assert result["status"] == "blocked", result
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("MODEL_NAME", raising=False)
    with agent_session(ToolService(a)) as run:
        result = run(goal="Run live")
    assert result["live_executed"] is False
    assert result["code"] == "MODEL_NOT_CONFIGURED"


def test_model_failure_keeps_committed_outputs(tmp_path):
    a = make_adapter(tmp_path)
    snapshot = base_snapshot(a)
    fake = ScriptedModel([call("publish_documents", {"snapshot": snapshot.model_dump(mode="json"),
        "baselines": baselines(a), "intent": "initial"})])
    # The next provider call fails after a real file-writing tool has committed.
    with agent_session(ToolService(a), fake) as run:
        result = run(goal="Prepare quote")
    assert result["status"] == "error" and result["code"] == "MODEL_OR_GRAPH_FAILED"
    assert len(result["outputs"]) == 4 and len(a.list_artifacts()) == 3
    assert all(a.read_bytes(f["file_id"]) for f in result["outputs"])


def test_graph_can_retry_only_failed_pdf_branch(tmp_path):
    a = make_adapter(tmp_path)
    snapshot = base_snapshot(a)
    service = ToolService(a, fail_formats={"pdf"})
    class RetryModel(ScriptedModel):
        def invoke(self, messages):
            if a.list_artifacts():
                service.fail_formats.clear()
            return super().invoke(messages)
    from navowork_agent.contracts import digest
    aid = "a_" + digest([a.context().case_id, "quotation"])[:24]
    fake = RetryModel([call("publish_documents", {"snapshot": snapshot.model_dump(mode="json"),
        "baselines": baselines(a), "intent": "initial"}),
        call("export_artifact", {"artifact_id": aid, "version": 1, "format": "pdf"}, "retry"), AIMessage(content="done")])
    with agent_session(service, fake) as run:
        result = run(goal="Prepare quote and retry failed export")
    assert result["status"] == "needs_review", result
    assert len(result["outputs"]) == 4 and {a["version"] for a in result["artifacts"]} == {1}


def test_agent_runtime_can_edit_and_validate_a_real_docx_copy(tmp_path):
    a = make_adapter(tmp_path)
    generated = publish(ToolService(a), base_snapshot(a))
    spec = next(artifact for artifact in generated.artifacts if artifact.kind == "spec")
    source = spec.files[0]
    created = invoke(ToolService(a), "create_working_copy", {"file_id": source.file_id}, "setup-working-docx")
    working = created.artifacts[0]
    model = ScriptedModel([
        call("list_context"),
        call("load_skill", {"name": "edit-documents"}, "edit-skill"),
        call("create_working_copy", {"file_id": source.file_id}, "copy-docx"),
        call("edit_file", {"artifact_id": working.artifact_id, "baseline": 1,
            "file_id": working.files[0].file_id, "operations": [{"op": "append_paragraph", "text": "Agent edited the working copy"}]}, "edit-docx"),
        call("validate_artifact", {"artifact_id": working.artifact_id, "version": 2}, "validate-docx"),
        AIMessage(content="The edited DOCX copy is ready for review.")])
    with agent_session(ToolService(a), model) as run:
        result = run(goal="Revise the specification DOCX and preserve its source version")
    details = [(v["status"], v.get("code")) for v in a._load()["results"].values()]
    assert result["status"] == "needs_review" and len(result["outputs"]) == 2, (
        result.get("code"), result.get("summary"), result.get("tool_steps"), model.calls, details)
    from docx import Document
    from io import BytesIO
    latest = Document(BytesIO(a.read_bytes(result["outputs"][-1]["file_id"])))
    assert "Agent edited the working copy" in " ".join(p.text for p in latest.paragraphs)
