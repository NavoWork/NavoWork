from sqlalchemy import func, select

from app.core import create_item, decode
from app.db import SessionLocal
from app.inquiry_assets import backfill_inquiry_assets
from app.models import Blob, Case, CaseAccess, Item, User
from app.workbench import append_artifact
from app.worker import work_once

BASE = "/api/v1/workspaces/ws_demo"


def library(client, case_id):
    response = client.get(BASE + "/library/assets")
    assert response.status_code == 200, response.text
    return [a for a in response.json()["items"] if a.get("inquiry", {}).get("id") == case_id]


def test_originals_and_attachments_are_persistent_and_access_scoped(client, other_client):
    case = client.post(BASE + "/inquiries", json={
        "title": "Archive inquiry", "customer": "Buyer", "originalText": "Need 600 blue bags"
    }).json()
    path = BASE + "/inquiries/" + case["id"]
    original = next(a for a in library(client, case["id"]) if a["sourceKind"] == "original")
    assert "600 blue bags" in client.get("/api/v1" + original["downloadPath"]).text
    evidence = client.post(path + "/evidence", data={"sourceRole": "customer_request"},
        files={"file": ("spec.csv", b"material,quantity\nCotton,600", "text/csv")})
    assert evidence.status_code == 200, evidence.text
    upload = client.post(path + "/canvas/files", files={
        "file": ("private.txt", b"Owner working notes", "text/plain")
    })
    assert upload.status_code == 200, upload.text
    assets = library(client, case["id"])
    source = next(a for a in assets if a["sourceKind"] == "evidence")
    private = next(a for a in assets if a["sourceKind"] == "canvas_file")
    assert client.get("/api/v1" + source["downloadPath"]).content == b"material,quantity\nCotton,600"
    assert client.get("/api/v1" + private["downloadPath"]).content == b"Owner working notes"
    assert not library(other_client, case["id"])
    assert other_client.get("/api/v1" + source["downloadPath"]).status_code == 404
    with SessionLocal() as db:
        other = db.scalar(select(User).where(User.email == "other@example.test"))
        db.add(CaseAccess(case_id=case["id"], user_id=other.id))
        db.commit()
    assert {a["id"] for a in library(other_client, case["id"])} == {original["id"], source["id"]}
    assert other_client.get("/api/v1" + private["downloadPath"]).status_code == 404
    # Favorites and file content survive new requests and do not depend on canvas state.
    assert client.put(BASE + f"/library/assets/{source['id']}/favorite", json={"starred": True}).status_code == 200
    assert next(a for a in library(client, case["id"]) if a["id"] == source["id"])["starred"]


def test_generated_versions_and_actual_export_bytes_are_archived(client, monkeypatch):
    monkeypatch.setattr("app.node_simulation.PHASE_SECONDS", 0)
    case = client.post(BASE + "/inquiries", json={"demoScenarioId": "us-tote"}).json()
    path = BASE + "/inquiries/" + case["id"]
    snapshots = []
    for revision in range(2):
        response = client.post(path + "/workbench/simulations", json={
            "node": "requirements", "baseRevision": revision, "instruction": "生成规格"
        })
        assert response.status_code == 200, response.text
        assert work_once(None)
        spec = next(a for a in library(client, case["id"])
                    if a["sourceId"] == f"artifact_{case['id']}_spec_v{revision + 1}")
        snapshots.append(spec)
        assert spec["version"] == revision + 1
        assert client.get("/api/v1" + spec["downloadPath"]).status_code == 200
    assert snapshots[0]["id"] == snapshots[1]["id"]
    assert "V1" in client.get("/api/v1" + snapshots[0]["downloadPath"]).text
    response = client.post(path + "/workbench/simulations", json={
        "node": "design", "baseRevision": 2, "instruction": "生成设计图"
    })
    assert response.status_code == 200, response.text
    assert work_once(None)
    exported = next(a for a in library(client, case["id"]) if a["mime"] == "image/png")
    from app.demo_images import preset_path
    assert client.get("/api/v1" + exported["downloadPath"]).content == preset_path("us-tote").read_bytes()


def test_backfill_is_idempotent_and_rollback_does_not_publish_assets(client):
    case_id = "inq_demo_bag"
    with SessionLocal() as db:
        case = db.get(Case, case_id)
        append_artifact(db, case, "spec", {"fields": {"product": "Cotton bag"}}, title="规格")
        db.commit()
        before = (db.scalar(select(func.count()).select_from(Item).where(Item.kind == "asset")),
                  db.scalar(select(func.count()).select_from(Blob)))
        backfill_inquiry_assets(db)
        backfill_inquiry_assets(db)
        db.commit()
        after = (db.scalar(select(func.count()).select_from(Item).where(Item.kind == "asset")),
                 db.scalar(select(func.count()).select_from(Blob)))
        assert before == after
        row = create_item(db, "evidence", {"title": "rolled-back", "text": "Must not appear"}, case_id=case_id)
        source_id = row.id
        db.rollback()
    assert not any(a["sourceId"] == source_id for a in library(client, case_id))


def test_repeated_attachment_does_not_duplicate_asset_and_revoked_access_blocks_download(client):
    path = BASE + "/inquiries/inq_demo_bag"
    for _ in range(2):
        assert client.post(path + "/evidence", files={
            "file": ("same.txt", b"same bytes", "text/plain")
        }).status_code == 200
    assets = [a for a in library(client, "inq_demo_bag") if a["name"] == "same.txt"]
    assert len(assets) == 1
    with SessionLocal() as db:
        db.query(CaseAccess).filter(CaseAccess.case_id == "inq_demo_bag").delete()
        db.commit()
    assert client.get("/api/v1" + assets[0]["downloadPath"]).status_code == 404
