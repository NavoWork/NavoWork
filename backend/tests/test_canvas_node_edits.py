import pytest

from app.worker import work_once
from test_node_simulation import no_provider
from test_inquiry_assets import library

BASE = "/api/v1/workspaces/ws_demo"


def create_case(client, scope="incomplete"):
    case = client.post(BASE + "/inquiries", json={"demoScenarioId": "us-tote", "demoDataScope": scope}).json()
    return case, BASE + "/inquiries/" + case["id"]


def simulate(client, path, node, **values):
    current = client.get(path).json()
    response = client.post(path + "/workbench/simulations", json={
        "node": node, "baseRevision": current["currentRevision"], "instruction": "保存本地节点草稿", **values,
    })
    assert response.status_code == 200, response.text
    assert response.json()["executionMode"] == "simulation"
    assert work_once(None)
    run = client.get(BASE + "/runs/" + response.json()["id"]).json()
    assert run["status"] == "succeeded", run
    assert run["agentVerification"]["modelApiCalled"] is False
    return client.get(path + "/workbench").json()


@pytest.mark.parametrize("node,kind", [("requirements", "spec"), ("competitor", "competitor_analysis"),
    ("costing", "quotation"), ("risks", "risk_review"), ("sample", "sample"), ("order", "order"), ("production", "production")])
def test_edited_document_survives_reload_history_and_asset_archive(client, no_provider, node, kind):
    case, path = create_case(client)
    before = simulate(client, path, node)
    edit = "产品：客户修改的帆布袋\n数量：6,000 件\n规格：待确认\n目的地：Seattle\n到货要求：待确认\n定制：蓝色标识"
    after = simulate(client, path, node, editedText=edit)
    artifact = after["artifacts"][kind]
    assert artifact["content"]["documentText"] == edit
    assert artifact["version"] == before["artifacts"][kind]["version"] + 1
    assert not client.get(path + "/revisions/1").json()["nodeArtifacts"][kind]["content"].get("documentText")
    assert client.get(path + "/revisions/2").json()["nodeArtifacts"][kind]["content"]["documentText"] == edit
    asset = next(a for a in library(client, case["id"]) if a["sourceId"] == artifact["itemId"])
    assert "客户修改的帆布袋" in client.get("/api/v1" + asset["downloadPath"]).text
    if node == "requirements":
        assert artifact["content"]["fields"]["quantity"] == "6000"
        assert artifact["content"]["fields"]["destination"] == "Seattle"
        assert artifact["content"]["fields"]["fabric"] is None
    stale = client.post(path + "/workbench/simulations", json={"node": node, "baseRevision": 1, "instruction": "旧草稿", "editedText": edit})
    assert stale.status_code == 409


@pytest.mark.parametrize("scope", ["incomplete", "reference"])
def test_prompt_regeneration_binds_each_saved_image_version_without_provider(client, no_provider, scope):
    case, path = create_case(client, scope)
    old = simulate(client, path, "design")["artifacts"]["concept_image"]
    prompt = "自然色帆布包，深蓝手提带，白色背景，正面与侧面展示。"
    new = simulate(client, path, "design", imagePrompt=prompt)["artifacts"]["concept_image"]
    assert new["content"]["prompt"] == prompt
    assert new["version"] == old["version"] + 1
    assert new["content"]["downloadUrl"] != old["content"]["downloadUrl"]
    assert new["content"]["imageApiCalled"] is False
    assert client.get(new["content"]["downloadUrl"]).content.startswith(b"\x89PNG")
    assert client.get(path + "/revisions/1").json()["nodeArtifacts"]["concept_image"]["content"]["prompt"] == old["content"]["prompt"]
    assets = library(client, case["id"])
    assert any(a["mime"] == "image/png" for a in assets)
    assert any(a["sourceId"] == new["itemId"] for a in assets)


def test_original_edit_after_generation_preserves_prior_original_and_adds_correction(client, no_provider):
    case, path = create_case(client)
    simulate(client, path, "requirements")
    current = client.get(path).json()
    response = client.patch(path, json={"metadataVersion": current["metadataVersion"], "originalText": "Customer correction: 6000 canvas bags"})
    assert response.status_code == 200, response.text
    assert client.get(path).json()["originalText"] == "Customer correction: 6000 canvas bags"
    originals = [a for a in library(client, case["id"]) if a["sourceKind"] == "original"]
    assert len(originals) == 2
    contents = [client.get("/api/v1" + a["downloadPath"]).text for a in originals]
    assert any("5,000" in text for text in contents)
    assert any("6000" in text for text in contents)


def test_invalid_edits_cannot_enqueue_or_fall_back_to_live_model(client, no_provider):
    _, path = create_case(client)
    for node, values in [("design", {"imagePrompt": " "}), ("design", {"imagePrompt": "x" * 6001}),
                         ("requirements", {"imagePrompt": "wrong node"}), ("design", {"editedText": "wrong action"})]:
        response = client.post(path + "/workbench/simulations", json={"node": node, "baseRevision": 0, "instruction": "测试", **values})
        assert response.status_code == 400
    assert not work_once(None)
