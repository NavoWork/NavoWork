from concurrent.futures import ThreadPoolExecutor

BASE = "/api/v1/workspaces/ws_demo"
CASE = BASE + "/inquiries/inq_demo_bag"


def run_worker(tmp_path):
    # Reopen the checkpoint DB on each call, just like restarting a worker.
    from langgraph.checkpoint.sqlite import SqliteSaver
    from app.agent import build_graph
    from app.worker import work_once
    with SqliteSaver.from_conn_string(str(tmp_path / "graph.sqlite3")) as saver:
        saver.setup()
        assert work_once(build_graph(saver))


def test_canvas_persists_files_and_cas_is_atomic(client, other_client):
    assert client.get(CASE + "/canvas").json() == {"editVersion": 0, "state": None}
    file = client.post(CASE + "/canvas/files", files={"file": ("note.txt", b"original attachment", "text/plain")}).json()
    state = {"schema": 1, "positions": {}, "tabs": [], "active": "canvas", "folders": [],
             "notes": [{"id": "note1", "title": "Memo", "text": "persist me", "folder": "notes"}], "files": [file], "drafts": {}, "results": []}
    saved = client.put(CASE + "/canvas", json={"editVersion": 0, "state": state})
    assert saved.status_code == 200, saved.text
    assert client.get(CASE + "/canvas").json()["state"]["notes"][0]["text"] == "persist me"
    assert client.get(CASE + f"/canvas/files/{file['serverFileId']}/download").content == b"original attachment"
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: client.put(CASE + "/canvas", json={"editVersion": 1, "state": state}).status_code, range(2)))
    assert sorted(results) == [200, 409]
    assert other_client.get(CASE + "/canvas").status_code == 404
    from app.db import SessionLocal
    from app.models import CaseAccess
    with SessionLocal() as db:
        db.add(CaseAccess(case_id="inq_demo_bag", user_id="other"))
        db.commit()
    assert other_client.get(CASE + "/canvas").json()["state"] is None
    assert other_client.get(CASE + f"/canvas/files/{file['serverFileId']}/download").status_code == 404
    assert other_client.put(CASE + "/canvas", json={"editVersion": 0, "state": state}).status_code == 404
    assert client.get(CASE).json()["currentRevision"] == 0  # Canvas save never grants business approval.
    assert client.put(CASE + "/canvas", json={"editVersion": 2, "state": {**state, "notes": "bad"}}).status_code == 400


def test_libraries_private_files_favorites_and_document_versions(client, other_client):
    private = client.post(BASE + "/library/assets", data={"space": "personal"}, files={"file": ("private.csv", b"a,b\n1,2", "text/csv")}).json()
    company = client.post(BASE + "/library/assets", data={"space": "company"}, files={"file": ("team.txt", b"shared", "text/plain")}).json()
    assert {v["id"] for v in other_client.get(BASE + "/library/assets").json()["items"]} == {company["id"]}
    assert private["id"] not in {v["id"] for v in other_client.get(BASE + "/assets").json()["items"]}
    assert other_client.get("/api/v1" + private["downloadPath"]).status_code == 404
    assert other_client.get("/api/v1" + company["downloadPath"]).content == b"shared"
    assert client.put(BASE + f"/library/assets/{company['id']}/favorite", json={"starred": True}).status_code == 200
    assert other_client.get(BASE + "/library/assets").json()["items"][0]["starred"] is False
    assert client.post(CASE + "/runs", json={"action": "analyze", "baseRevision": 0, "assetVersionIds": [private["assetVersionId"]]}).status_code == 422
    doc = client.post(BASE + "/library/documents", json={"title": "Test SOP", "folder": "业务流程", "content": "# Original\nConfirm material"}).json()
    assert client.put(BASE + f"/library/documents/{doc['id']}/favorite", json={"starred": True}).status_code == 200
    assert other_client.get(BASE + "/library/documents").json()["items"][0]["starred"] is False
    edited = client.post(BASE + f"/library/documents/{doc['id']}/versions", json={"baseVersion": 1, "title": "Test SOP", "folder": "业务流程", "content": "Updated"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["version"] == 2
    assert client.get(BASE + f"/sources/{doc['id']}/versions/1").json()["content"].startswith("# Original")
    assert client.post(BASE + f"/library/documents/{doc['id']}/versions", json={"baseVersion": 1}).status_code == 409


def test_snapshot_progress_and_proposal_acceptance(client, tmp_path):
    doc = client.post(BASE + "/library/documents", json={"title": "SOP", "folder": "业务流程", "content": "Check the bag"}).json()
    run = client.post(CASE + "/runs", json={"baseRevision": 0, "action": "analyze", "sourceVersionIds": [doc["sourceVersionId"]]}).json()
    assert client.patch(BASE + f"/sources/{doc['id']}/versions/1", json={"editVersion": 1, "content": "Changed in place"}).status_code == 409
    # Later evidence must not change the dispatched task.
    client.post(CASE + "/evidence", json={"sourceRole": "internal_note", "title": "Later", "text": "999 handbags"})
    run_worker(tmp_path)
    finished = client.get(BASE + f"/runs/{run['id']}").json()
    assert finished["status"] == "succeeded", finished
    rev = client.get(CASE + "/revisions").json()["items"][-1]
    assert rev["requirements"]["quantity"] == 3000
    assert rev["sourceRefs"][0]["sourceVersionId"] == doc["sourceVersionId"]
    assert rev["inputManifest"]["evidence"] == []
    events = client.get(BASE + f"/runs/{run['id']}/events").json()["items"]
    assert {e["payload"]["phase"] for e in events} >= {"retrieving", "composing", "validating", "committing"}
    body = {"baseRevision": 1, "action": "accept_proposal", "proposalRef": {"proposalId": rev["proposal"]["proposalId"], "version": 1}, "acceptanceEvidence": "Customer confirms this product direction"}
    accepted = client.post(CASE + "/runs", json=body)
    assert accepted.status_code == 200, accepted.text  # No supplier/cost requirement for accepting a proposal.
    run_worker(tmp_path)
    result = client.get(CASE + "/revisions").json()["items"][-1]
    assert result["proposal"]["status"] == "accepted"
    assert result["quote"] is None
    assert client.get(CASE + "/approvals").json()["items"] == []


def test_clarification_survives_restart_and_resumes_same_run(client, tmp_path):
    run = client.post(CASE + "/runs", json={"baseRevision": 0, "action": "analyze", "instruction": "请核算报价"}).json()
    run_worker(tmp_path)
    paused = client.get(BASE + f"/runs/{run['id']}").json()
    assert paused["status"] == "needs_input", paused
    assert client.get(CASE).json()["pendingRunId"] == run["id"]
    assert client.post(CASE + "/runs", json={"baseRevision": 0, "action": "analyze"}).status_code == 409
    evidence = client.post(CASE + "/evidence", json={"sourceRole": "supplier_quote", "title": "Factory", "text": "44 + 2 CNY"}).json()
    offer = client.post(CASE + "/supplier-offers", json={"supplier": "Factory", "evidenceSourceId": evidence["id"], "baseCny": "44", "packagingCny": "2", "localCny": "4", "moq": 1000}).json()
    answer = {"baseRevision": 0, "replyToRunId": run["id"], "answers": [{"questionId": "cost_parameters", "value": "已核对工厂成本"}], "selectedSupplierOfferId": offer["id"], "costInputs": {"exchangeRate": "7.2", "margin": "20", "quantity": 3000}}
    resumed = client.post(CASE + "/runs", json=answer)
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["id"] == run["id"]
    run_worker(tmp_path)
    final = client.get(BASE + f"/runs/{run['id']}").json()
    assert final["status"] == "succeeded", final
    assert "calculating" in final["completedPhases"]
    assert client.get(CASE + "/revisions").json()["items"][-1]["quote"]["unitPriceMinor"] == 869
    assert client.post(CASE + "/runs", json=answer).status_code == 409


def test_cancel_without_body_capabilities_and_unknown_product(client, tmp_path):
    unknown = client.post(BASE + "/inquiries", json={"title": "Incomplete", "customer": "Buyer", "originalText": "Please help with a new order"}).json()
    path = BASE + "/inquiries/" + unknown["id"]
    run = client.post(path + "/runs", json={"baseRevision": 0, "action": "analyze"}).json()
    run_worker(tmp_path)
    assert client.get(BASE + f"/runs/{run['id']}").json()["status"] == "needs_input"
    cancelled = client.post(BASE + f"/runs/{run['id']}/cancel")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert not client.get(path).json().get("pendingRunId")
    client.patch(BASE + "/capabilities/agent", json={"enabled": False})
    assert client.post(path + "/runs", json={"baseRevision": 0}).status_code == 422
    assert client.get(BASE + "/skill-market").json()["items"][0]["status"] == "disabled"


def test_conversation_keeps_prior_facts_and_routes_change_to_sop(client, tmp_path):
    first = client.post(CASE + "/runs", json={"baseRevision": 0, "instruction": "先试单300件背包"}).json()
    run_worker(tmp_path)
    assert client.get(BASE + f"/runs/{first['id']}").json()["status"] == "succeeded"
    assert client.get(CASE + "/revisions").json()["items"][-1]["requirements"]["quantity"] == 300
    client.post(CASE + "/runs", json={"baseRevision": 1, "action": "revise", "instruction": "请继续列出缺失规格"})
    run_worker(tmp_path)
    assert client.get(CASE + "/revisions").json()["items"][-1]["requirements"]["quantity"] == 300
    change_run = client.post(CASE + "/runs", json={"baseRevision": 2, "action": "revise", "instruction": "包装改为彩盒，请分析影响"}).json()
    run_worker(tmp_path)
    assert client.get(BASE + f"/runs/{change_run['id']}").json()["status"] == "succeeded"
    change = client.get(CASE + "/change-sets").json()["items"][0]
    assert change["status"] == "awaiting_confirmation"
    assert "calculate_cost" in {n["nodeKey"] for n in change["nodeImpacts"]}
    assert all(isinstance(n["reason"], list) for n in change["nodeImpacts"])
