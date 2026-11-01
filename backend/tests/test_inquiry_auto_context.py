"""Node generation needs no source picker and stays within the inquiry scope."""
from app.core import decode
from app.db import SessionLocal
from app.models import Case, Job, Run, User
from app.run_context import prepare_context
from test_workbench_v2 import _start

BASE = "/api/v1/workspaces/ws_demo"


def test_agent_automatically_reads_current_sources_and_saved_canvas(client):
    current = client.post(BASE + "/inquiries", json={"demoScenarioId": "de-backpack"}).json()
    foreign = client.post(BASE + "/inquiries", json={"demoScenarioId": "de-backpack"}).json()
    path = BASE + "/inquiries/" + current["id"]
    foreign_path = BASE + "/inquiries/" + foreign["id"]
    foreign_view = client.get(foreign_path + "/workbench").json()
    foreign_refs = {row["id"] for row in foreign_view["knowledge"] if row.get("caseId") == foreign["id"]}

    attachment = client.post(path + "/canvas/files", files={"file": ("packing.txt", b"Use recycled cartons", "text/plain")}).json()
    saved = client.put(path + "/canvas", json={"editVersion": 0, "state": {"schema": 1,
        "files": [{**attachment, "folder": "attachments"}]}})
    assert saved.status_code == 200, saved.text
    foreign_attachment = client.post(foreign_path + "/canvas/files", files={"file": ("secret.txt", b"Other customer", "text/plain")}).json()
    company = client.post(BASE + "/library/assets", data={"space": "company"}, files={"file": ("team.txt", b"Shared packing standard", "text/plain")}).json()
    personal = client.post(BASE + "/library/assets", data={"space": "personal"}, files={"file": ("private.txt", b"Private document", "text/plain")}).json()
    document = client.post(BASE + "/library/documents", json={"title": "Packing SOP", "folder": "业务流程", "content": "Old standard"}).json()
    assert client.post(BASE + f"/sources/{document['id']}/versions/1/publish").status_code == 200
    updated = client.post(BASE + f"/library/documents/{document['id']}/versions", json={"baseVersion": 1,
        "title": "Packing SOP", "folder": "业务流程", "content": "Current packing standard"})
    assert updated.status_code == 200, updated.text
    assert client.post(BASE + f"/sources/{document['id']}/versions/2/publish").status_code == 200

    toolbox, _, job_id, _, case_id = _start(client, path, "requirements", "读取本询盘全部资料，整理规格")
    with SessionLocal() as db:
        payload = decode(db.get(Job, job_id).payload)
        assert len(payload["evidence"]) == 4
        assert not foreign_refs.intersection(ref["sourceVersionId"] for ref in payload["sourceRefs"])
        versions = [ref["version"] for ref in payload["sourceRefs"] if ref["sourceId"] == document["id"]]
        assert versions == [2]
        assert {row["id"] for row in payload["canvasManifest"]} == {attachment["serverFileId"]}
        assert company["assetVersionId"] in {row["id"] for row in payload["assetManifest"]}
        assert personal["assetVersionId"] not in {row["id"] for row in payload["assetManifest"]}
        # A legacy client selecting a subset no longer narrows automatic context.
        context = prepare_context(db, db.get(User, toolbox.user_id), db.get(Case, case_id),
            {"contextScope": "inquiry", "inputRefs": [payload["evidence"][0]["id"]]})
        assert {row["id"] for row in context["evidence"]} == {row["id"] for row in payload["evidence"]}

    context = toolbox.call("get_case_context", {})["data"]
    assert {row["id"] for row in context["canvasFiles"]} == {attachment["serverFileId"]}
    assert len(context["projectKnowledge"]) == 2
    assert not foreign_refs.intersection(row["id"] for row in context["knowledge"])
    read = toolbox.call("read_source", {"source_id": attachment["serverFileId"]})
    assert read["status"] == "success" and read["data"]["text"] == "Use recycled cartons"
    for source_id in [*foreign_refs, foreign_attachment["serverFileId"], foreign_view["evidence"][0]["id"]]:
        denied = toolbox.call("read_source", {"source_id": source_id})
        assert denied["code"] == "SOURCE_NOT_FOUND", denied
    visible = client.get(path + "/workbench").json()["knowledge"]
    assert not foreign_refs.intersection(row["id"] for row in visible)


def test_legacy_node_generation_also_includes_all_inquiry_references(client):
    inquiry = client.post(BASE + "/inquiries", json={"demoScenarioId": "de-backpack"}).json()
    path = BASE + "/inquiries/" + inquiry["id"]
    response = client.post(path + "/node-generations", json={"node": "risks", "baseRevision": 0,
        "contextScope": "inquiry", "instruction": "读取当前询盘全部资料，整理风险"})
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        run = db.get(Run, response.json()["id"])
        payload = decode(db.get(Job, run.job_id).payload)
        assert len(payload["evidence"]) == 4
        assert len(payload["sourceRefs"]) >= 2
        assert payload["generationTarget"] == "risks"
