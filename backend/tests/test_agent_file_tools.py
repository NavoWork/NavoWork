"""Real host services and files, explicitly offline model/tool verification."""
from pathlib import Path
import sys
from io import BytesIO
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent-kit/tests"))
from support import base_snapshot, change_snapshot, publish, invoke, INPUTS, baselines
from test_runtime import ScriptedModel, call
from langchain_core.messages import AIMessage

BASE = "/api/v1/workspaces/ws_demo"
CASE = BASE + "/inquiries/inq_demo_bag"


def upload(client, name, canvas=False):
    p = INPUTS / "BAG-2026-DE-001" / name
    import mimetypes
    response = client.post(CASE + ("/canvas/files" if canvas else "/evidence"),
        data={} if canvas else {"sourceRole": "supplier_quote"},
        files={"file": (p.name, p.read_bytes(), mimetypes.guess_type(p.name)[0] or "application/octet-stream")})
    assert response.status_code == 200, response.text
    return response.json()


def start(client, instruction="准备报价，汇率7.20，毛利20%", canvas_refs=None):
    response = client.post(CASE + "/runs", json={"action": "analyze", "instruction": instruction,
        "baseRevision": client.get(CASE).json()["currentRevision"], "canvasFileIds": canvas_refs or []})
    assert response.status_code == 200, response.text
    return response.json()


def claim(run_id):
    from app.worker import claim_work
    from app.agent_files import HostAdapter
    from app.db import SessionLocal
    from app.models import Run, Job
    from app.core import decode
    from navowork_agent.contracts import ExecutionContext
    item_id, generation = claim_work("file-test")
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        job = db.get(Job, run.job_id)
        run.status, job.status = "running", "running"
        db.commit()
        context = ExecutionContext(case_id=run.case_id, job_id=job.id, run_id=run.id, generation=generation)
        return HostAdapter(context, decode(job.payload)["createdBy"], item_id)


class InputFacade:
    def __init__(self, adapter): self.adapter = adapter
    def import_source(self, path):
        return next(f for f in self.adapter.list_files() if f.name == path.name)
    def read_document(self, file_id): return self.adapter.read_document(file_id)


def result_dict(result):
    return {**result.model_dump(mode="json"), "live_executed": False, "verification_mode": "offline_tool_test",
            "summary": f"Recorded {len(result.outputs)} actual generated files; draft review required."}


def test_host_blob_artifact_events_and_download_authorization(client, other_client, monkeypatch):
    monkeypatch.setenv("AGENT_FILE_TOOLS", "1")
    from app.agent_files import confirmed_facts
    assert confirmed_facts("如果毛利20%会怎样") == {}
    assert confirmed_facts("汇率7.20，毛利20%") == {"fx": "7.20", "margin": "0.2"}
    # Support fixture expects exact host decimal string, so explicitly set 0.20 below.
    for name in ("inquiry.eml", "factory-A-quote.xlsx"): upload(client, name)
    run = start(client)
    a = claim(run["id"])
    from app.db import SessionLocal
    from app.models import Job, WorkItem
    from app.core import decode, encode
    with SessionLocal() as db:
        job = db.get(Job, a.context().job_id)
        data = decode(job.payload)
        data["agentFacts"]["margin"] = "0.20"
        job.payload = encode(data)
        db.commit()
    from navowork_agent.tools.service import ToolService
    snap = base_snapshot(InputFacade(a))
    svc = ToolService(a)
    first = publish(svc, snap, key="once")
    assert first.status == "needs_review" and len(first.outputs) == 4, first
    assert publish(svc, snap, key="once", bases={"spec": 0, "cost": 0, "quotation": 0}) == first
    # A newly uploaded attachment is not part of the frozen manifest until a new input attempt.
    later = upload(client, "change-color-box.eml")
    assert later["id"] not in {f.file_id for f in a.list_files()}
    assert invoke(svc, "read_document", {"file_id": later["id"]}).code == "FILE_UNAVAILABLE"
    from app.file_worker import finish_file_work
    finish_file_work(a, result_dict(first))
    view = client.get(BASE + "/runs/" + run["id"]).json()
    assert view["status"] == "succeeded" and len(view["fileOutputs"]) == 4
    assert view["agentVerification"]["liveExecuted"] is False
    data = client.get(view["fileOutputs"][0]["downloadUrl"]).content
    assert data.startswith(b"PK")
    assert other_client.get(view["fileOutputs"][0]["downloadUrl"]).status_code == 404
    rev = client.get(CASE + "/revisions").json()["items"][-1]
    assert rev["quote"]["unitPriceMinor"] == 869 and rev["quote"]["goodsSubtotalMinor"] == 2607000
    quote_row = next(v for v in client.get(CASE + "/artifacts").json()["items"] if v["kind"] == "quotation")
    exported = client.post(CASE + f"/artifacts/{quote_row['id']}/exports", json={"format": "xlsx"})
    assert exported.status_code == 200
    from openpyxl import load_workbook
    wb = load_workbook(BytesIO(client.get(exported.json()["downloadUrl"]).content))
    text = " ".join(str(c.value) for ws in wb for row in ws for c in row)
    assert "INTERNAL_COST_MARGIN_DO_NOT_EXPORT" not in text and "Factory A" not in text
    assert "8.69" in text and "26070.00" in text
    # A finished lease cannot be used to write or even publish new run events.
    stale = publish(svc, snap, "confirmed_change", bases={"spec": 1, "cost": 1, "quotation": 1})
    assert stale.code == "STALE_CONTEXT"
    change_run = start(client, "按邮件变更包装，缺价先提问")
    change = claim(change_run["id"])
    assert change.user_facts() == {"fx": "7.20", "margin": "0.2"}
    assert {r["ref"]["version"] for r in change.list_artifacts()} == {1}


def test_real_host_pause_resume_same_job_and_versions(client, tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_FILE_TOOLS", "1")
    monkeypatch.setenv("FILE_GRAPH_CHECKPOINT_DB", str(tmp_path / "files.sqlite3"))
    for name in ("inquiry.eml", "factory-A-quote.xlsx", "change-color-box.eml"): upload(client, name)
    run = start(client)
    a = claim(run["id"])
    from app.db import SessionLocal
    from app.models import Job
    from app.core import decode, encode
    with SessionLocal() as db:
        job = db.get(Job, a.context().job_id)
        data = decode(job.payload); data["agentFacts"]["margin"] = "0.20"; job.payload = encode(data); db.commit()
    snap = change_snapshot(InputFacade(a), base_snapshot(InputFacade(a)))
    from app.file_worker import execute_file_work
    waiting = execute_file_work(a.work_item_id, a.context().generation, model=ScriptedModel([
        call("publish_documents", {"snapshot": snap.model_dump(mode="json"), "baselines": baselines(a), "intent": "initial"})]))
    assert waiting["status"] == "needs_info", waiting
    view = client.get(BASE + "/runs/" + run["id"]).json()
    assert view["status"] == "needs_input" and len(view["fileOutputs"]) == 4
    old_urls = [f["downloadUrl"] for f in view["fileOutputs"]]
    original = [client.get(u).content for u in old_urls]
    upload(client, "factory-A-color-box-update.eml")
    response = client.post(CASE + "/runs", json={"baseRevision": 0, "replyToRunId": run["id"],
        "answers": [{"questionId": q["id"], "value": "工厂补价邮件已上传"} for q in view["clarification"]["questions"]]})
    assert response.status_code == 200, response.text  # No manual supplier offer or costs required.
    resumed = claim(run["id"])
    priced = change_snapshot(InputFacade(resumed), snap, priced=True)
    result = execute_file_work(resumed.work_item_id, resumed.context().generation, model=ScriptedModel([
        call("publish_documents", {"snapshot": priced.model_dump(mode="json"), "baselines": baselines(resumed), "intent": "confirmed_change"}), AIMessage(content="done")]))
    assert result["status"] == "needs_review", result
    view = client.get(BASE + "/runs/" + run["id"]).json()
    assert view["status"] == "succeeded" and len(view["fileOutputs"]) == 8
    assert all(client.get(u).content == data for u, data in zip(old_urls, original))
    artifacts = client.get(CASE + "/artifacts").json()["items"]
    assert len(artifacts) == 6
    quote = client.get(CASE + "/revisions").json()["items"][-1]["quote"]
    assert quote["unitPriceMinor"] == 921 and quote["goodsSubtotalMinor"] == 2763000


def test_canvas_manifest_and_no_model_no_fake_success(client, monkeypatch):
    monkeypatch.setenv("AGENT_FILE_TOOLS", "1")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("MODEL_NAME", raising=False)
    attachment = upload(client, "inquiry.eml", canvas=True)
    run = start(client, canvas_refs=[attachment["serverFileId"]])
    a = claim(run["id"])
    assert any(f.name == "inquiry.eml" for f in a.list_files())
    from app.file_worker import execute_file_work
    result = execute_file_work(a.work_item_id, a.context().generation)
    assert result["code"] == "MODEL_NOT_CONFIGURED" and result["live_executed"] is False
    assert client.get(BASE + "/runs/" + run["id"]).json()["status"] == "failed"
    assert client.get(CASE + "/artifacts").json()["items"] == []


def test_workbench_agent_mode_uses_file_capable_tool_loop(client, monkeypatch):
    response = client.post(CASE + "/runs", json={"action": "analyze", "instruction": "修改已上传的产品规格文件",
        "baseRevision": client.get(CASE).json()["currentRevision"], "agentMode": True})
    assert response.status_code == 200, response.text
    run_id = response.json()["id"]
    calls = []

    def execute_agent_work(item_id, generation):
        calls.append((item_id, generation))

    def unexpected_file_agent(*args, **kwargs):
        raise AssertionError("Workbench must preserve its existing business tool loop")

    monkeypatch.setattr("app.file_worker.execute_file_work", unexpected_file_agent)
    monkeypatch.setattr("app.agent_runtime.execute_agent_work", execute_agent_work)
    from app.worker import work_once

    assert work_once(None)
    assert len(calls) == 1
    view = client.get(BASE + "/runs/" + run_id).json()
    assert view["status"] == "running"


def test_workbench_chat_edits_uploaded_docx_and_preserves_source(client, tmp_path, monkeypatch):
    from docx import Document
    from app.agent_runtime import execute_agent_work
    monkeypatch.setenv("WORKBENCH_AGENT_CHECKPOINT_DB", str(tmp_path / "workbench.sqlite3"))

    source_doc = Document()
    source_doc.add_paragraph("Product: travel bag")
    buffer = BytesIO()
    source_doc.save(buffer)
    uploaded = client.post(CASE + "/evidence", files={"file": ("product-spec.docx", buffer.getvalue(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert uploaded.status_code == 200, uploaded.text
    source_id = uploaded.json()["id"]
    run_response = client.post(CASE + "/runs", json={"action": "analyze", "instruction": "Add a reviewed note to the end of the specification document",
        "baseRevision": client.get(CASE).json()["currentRevision"], "agentMode": True})
    assert run_response.status_code == 200, run_response.text
    adapter = claim(run_response.json()["id"])
    original_bytes = adapter.read_bytes(source_id)

    class EditingChatModel:
        def __init__(self):
            self.stage = 0

        def bind_tools(self, schemas):
            names = {schema["function"]["name"] for schema in schemas}
            assert {"file_create_working_copy", "file_edit_file", "file_validate_artifact", "update_requirements", "calculate_cost", "record_order"} <= names
            return self

        def invoke(self, messages):
            if self.stage == 0:
                self.stage += 1
                return call("file_list_context", id="context")
            result = __import__("json").loads(messages[-1].content)
            if self.stage == 1:
                source = next(file for file in result["data"]["files"] if file["file_id"] == source_id)
                self.stage += 1
                return call("file_create_working_copy", {"file_id": source["file_id"]}, id="copy")
            if self.stage == 2:
                artifact, output = result["artifacts"][0], result["outputs"][0]
                self.stage += 1
                return call("file_edit_file", {"artifact_id": artifact["artifact_id"], "baseline": artifact["version"],
                    "file_id": output["file_id"], "operations": [{"op": "append_paragraph", "text": "Reviewed by agent"}]}, id="edit")
            if self.stage == 3:
                artifact = result["artifacts"][0]
                self.stage += 1
                return call("file_validate_artifact", {"artifact_id": artifact["artifact_id"], "version": artifact["version"]}, id="validate")
            return AIMessage(content="Created and validated a separate working copy.")

    execute_agent_work(adapter.work_item_id, adapter.context().generation, model=EditingChatModel())
    from app.core import decode
    from app.db import SessionLocal
    from app.models import Blob, Item
    with SessionLocal() as db:
        source_record = decode(db.get(Item, source_id).payload)
        source_blob = db.get(Blob, source_record["blobId"])
        assert Path(source_blob.path).read_bytes() == original_bytes
    view = client.get(BASE + "/runs/" + run_response.json()["id"]).json()
    assert view["status"] == "succeeded" and len(view["fileOutputs"]) == 2
    edited_output = next(file for file in view["fileOutputs"] if "working-v2" in file["name"])
    edited_bytes = client.get(edited_output["downloadUrl"]).content
    edited_doc = Document(BytesIO(edited_bytes))
    assert "Reviewed by agent" in " ".join(paragraph.text for paragraph in edited_doc.paragraphs)


def test_selected_assets_resources_and_revocation(client, monkeypatch):
    monkeypatch.setenv("AGENT_FILE_TOOLS", "1")
    pasted = client.post(CASE + "/evidence", json={"title": "Supplier note", "text": "Lead time is unknown."}).json()
    asset = client.post(BASE + "/library/assets", data={"space": "company"},
        files={"file": ("selected.txt", b"Supplier terms: deposit 30%", "text/plain")})
    assert asset.status_code == 200, asset.text
    asset_id = asset.json()["assetVersionId"]
    private = client.post(BASE + "/library/assets", data={"space": "personal"},
        files={"file": ("private.txt", b"private material", "text/plain")}).json()
    body = {"instruction": "准备报价", "action": "analyze", "baseRevision": 0,
        "assetVersionIds": [private["assetVersionId"]]}
    assert client.post(CASE + "/runs", json=body).status_code == 422
    resource = client.post(BASE + "/library/documents", json={"title": "Trade terms", "folder": "Terms",
        "content": "Do not guarantee arrival before confirmation."})
    assert resource.status_code == 200, resource.text
    rid = resource.json()["sourceVersionId"]
    body.update(assetVersionIds=[asset_id], sourceVersionIds=[rid])
    run = client.post(CASE + "/runs", json=body)
    assert run.status_code == 200, run.text
    a = claim(run.json()["id"])
    refs = {f.file_id: f for f in a.list_files()}
    assert asset_id in refs and rid in refs and private["assetVersionId"] not in refs
    assert a.read_document(asset_id)["sections"][0]["text"] == "Supplier terms: deposit 30%"
    assert "arrival" in a.read_document(rid)["sections"][0]["text"]
    assert a.read_document(pasted["id"])["sections"][0]["text"] == "Lead time is unknown."
    instruction = next(fid for fid in refs if fid.startswith("job_message:"))
    assert a.read_document(instruction)["sections"][0]["text"] == "准备报价"
    from app.db import SessionLocal
    from app.models import Item
    from app.core import decode, encode
    with SessionLocal() as db:
        row = db.get(Item, rid)
        row.payload = encode({**decode(row.payload), "status": "revoked"})
        db.commit()
    from navowork_agent.contracts import AgentError
    with pytest.raises(AgentError, match="revoked"):
        a.read_bytes(rid)


def test_agent_can_continue_from_human_office_versions_and_native_exports(client):
    from docx import Document
    from app.db import SessionLocal
    from app.exports import export_artifact
    from app.models import Case, Item
    from app.workbench import append_artifact

    document = Document()
    document.add_paragraph("Original")
    buffer = BytesIO()
    document.save(buffer)
    source = client.post(CASE + "/evidence", files={"file": ("human.docx", buffer.getvalue(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}).json()
    office_path = CASE + "/workbench/office"
    copied = client.post(office_path, json={"fileId": source["id"]}).json()
    saved = client.put(office_path + "/" + copied["documentId"], json={"baseVersion": 1, "baseHash": copied["sha256"],
        "operations": [{"op": "set_paragraph", "index": 0, "text": "Human revised"}]})
    assert saved.status_code == 200, saved.text
    office_id = copied["documentId"] + ":v2"
    with SessionLocal() as db:
        case = db.get(Case, "inq_demo_bag")
        spec = append_artifact(db, case, "spec", {"fields": {"product": "Canvas bag"}})
        exported = export_artifact(db, case, db.get(Item, spec["itemId"]), "docx")
    adapter = claim(start(client)["id"])
    refs = {ref.file_id: ref for ref in adapter.list_files()}
    assert office_id in refs and exported["exportId"] in refs
    assert adapter.read_document(office_id)["sections"][0]["text"] == "Human revised"
    assert Document(BytesIO(adapter.read_bytes(exported["exportId"]))).tables[0].cell(1, 1).text == "Canvas bag"
    assert adapter.read_bytes(office_id) == client.get(saved.json()["downloadUrl"]).content
