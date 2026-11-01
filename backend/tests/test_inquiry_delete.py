from concurrent.futures import ThreadPoolExecutor

from app.core import decode
from app.db import SessionLocal
from app.models import Case, CaseAccess
from app.worker import work_once
from test_node_simulation import no_provider
from test_inquiry_assets import library

BASE = "/api/v1/workspaces/ws_demo"


def create(client):
    case = client.post(BASE + "/inquiries", json={"title": "Delete and restore", "customer": "Buyer", "originalText": "500 canvas bags"}).json()
    return case, BASE + "/inquiries/" + case["id"]


def test_delete_hides_list_summary_and_detail_but_restore_preserves_history_and_assets(client, no_provider):
    case, path = create(client)
    assert client.post(path + "/workbench/simulations", json={"node": "requirements", "baseRevision": 0, "instruction": "模拟"}).status_code == 200
    assert work_once(None)
    history = client.get(path + "/revisions").json()
    assets = library(client, case["id"])
    before = client.get(BASE + "/inquiries/summary").json()["active"]
    deleted = client.delete(path)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deletedAt"]
    assert client.get(path).status_code == 404
    assert client.get(path + "/revisions").status_code == 404
    assert case["id"] not in {row["id"] for row in client.get(BASE + "/inquiries").json()["items"]}
    assert client.get(BASE + "/inquiries/summary").json()["active"] == before - 1
    trash = client.get(BASE + "/inquiries?deleted=true&q=Delete").json()
    assert trash["matchedCount"] == 1 and trash["items"][0]["id"] == case["id"]
    assert client.delete(path).json()["metadataVersion"] == deleted.json()["metadataVersion"]
    assert library(client, case["id"]) == assets
    assert client.get("/api/v1" + assets[0]["downloadPath"]).status_code == 200
    restored = client.post(path + "/restore", json={})
    assert restored.status_code == 200, restored.text
    assert not restored.json().get("deletedAt")
    assert client.get(path + "/revisions").json() == history
    assert client.get(BASE + "/inquiries/summary").json()["active"] == before
    assert client.get(BASE + "/inquiries?deleted=true").json()["matchedCount"] == 0


def test_only_owner_or_accessible_admin_can_delete_and_restore(client, other_client):
    case, path = create(client)
    assert other_client.delete(path).status_code == 404
    assert other_client.post(path + "/restore", json={}).status_code == 404
    with SessionLocal() as db:
        db.add(CaseAccess(case_id=case["id"], user_id="other"))
        db.commit()
    assert other_client.delete(path).status_code == 403
    assert client.delete(path).status_code == 200
    assert other_client.post(path + "/restore", json={}).status_code == 403
    own, own_path = create(other_client)
    assert other_client.delete(own_path).status_code == 200
    assert other_client.post(own_path + "/restore", json={}).status_code == 200


def test_delete_rejects_running_and_waiting_input_tasks(client):
    case, path = create(client)
    run = client.post(path + "/workbench/simulations", json={"node": "requirements", "baseRevision": 0, "instruction": "模拟"}).json()
    assert client.delete(path).status_code == 409
    assert client.get(path).status_code == 200
    client.post(BASE + "/runs/" + run["id"] + "/cancel")
    from app.core import encode
    with SessionLocal() as db:
        row = db.get(Case, case["id"])
        row.payload = encode({**decode(row.payload), "pendingRunId": "pending-test"})
        db.commit()
    assert client.delete(path).status_code == 409


def test_delete_and_start_run_cannot_both_win(client):
    case, path = create(client)
    with ThreadPoolExecutor(2) as pool:
        deletion = pool.submit(client.delete, path)
        execution = pool.submit(client.post, path + "/workbench/simulations", json={"node": "requirements", "baseRevision": 0, "instruction": "模拟"})
        statuses = (deletion.result().status_code, execution.result().status_code)
    assert statuses in ((200, 404), (409, 200)), statuses
    with SessionLocal() as db:
        row = db.get(Case, case["id"])
        assert not (decode(row.payload).get("deletedAt") and row.active_run_id)
