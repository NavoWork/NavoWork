BASE = "/api/v1/workspaces/ws_demo"
CASE = BASE + "/inquiries/inq_demo_bag"


def run_worker(tmp_path):
    from langgraph.checkpoint.sqlite import SqliteSaver
    from app.agent import build_graph
    from app.worker import work_once
    with SqliteSaver.from_conn_string(str(tmp_path / "nodes.sqlite3")) as saver:
        assert work_once(build_graph(saver))


def checked(response):
    assert response.status_code == 200, response.text
    return response.json()


def test_generate_restore_and_continue_preserves_other_nodes(client, tmp_path):
    evidence = checked(client.post(CASE + "/evidence", json={"title": "Supplier", "sourceRole": "supplier_quote", "text": "3000 backpacks; base CNY44, packaging CNY2, factory A"}))
    offer = checked(client.post(CASE + "/supplier-offers", json={"supplier": "A", "evidenceSourceId": evidence["id"], "baseCny": "44", "packagingCny": "2", "localCny": "4", "moq": 1000}))
    wiki = checked(client.post(BASE + "/knowledge", json={"title": "Quote rule", "content": "Unknown freight must remain pending"}))
    refs = [f"{wiki['sourceId']}:v1"]

    def generate(node, revision, **extra):
        run = checked(client.post(CASE + "/node-generations", json={"node": node, "baseRevision": revision, "inputRefs": [evidence["id"]], "sourceVersionIds": refs, **extra}))
        assert client.post(CASE + f"/revisions/{max(1, revision)}/restore", json={"baseRevision": revision}).status_code in (404, 409)
        run_worker(tmp_path)
        assert checked(client.get(BASE + f"/runs/{run['id']}"))["status"] == "succeeded"
        return checked(client.get(CASE + f"/revisions/{revision+1}"))

    first = generate("requirements", 0)
    second = generate("quote", 1, selectedSupplierOfferId=offer["id"], costInputs={"exchangeRate": "7.2", "margin": "20", "quantity": 3000})
    assert second["quote"]["unitPriceMinor"] == 869
    assert second["artifactVersionIds"]["spec"] == first["artifactVersionIds"]["spec"]
    assert second["inputManifest"]["evidence"][0]["id"] == evidence["id"]
    checked(client.put(CASE + "/revisions/2/reply-drafts/en-US", json={"baseDraftVersion": 1, "text": "Human edited reply; no delivery guarantee."}))
    third = generate("risks", 2)
    assert third["quote"] == second["quote"]
    assert checked(client.get(CASE + "/revisions/3/reply-drafts/en-US"))["text"].startswith("Human edited")

    cleared = checked(client.post(CASE + "/revisions/1/restore", json={"baseRevision": 3, "target": "quote"}))
    assert cleared["quote"] is None
    cleared_quote = checked(client.get(CASE + "/artifacts/" + cleared["artifactVersionIds"]["quotation"]))
    assert cleared_quote["content"]["pendingReconfirmation"]
    assert checked(client.post(CASE + f"/artifacts/{cleared_quote['id']}/validate", json={}))["status"] == "blocked"
    assert cleared["requirements"] == third["requirements"]

    fork = checked(client.post(CASE + "/revisions/2/restore", json={"baseRevision": 4, "target": "all"}))
    assert fork["parentRevision"] == 4 and fork["restoredFromRevision"] == 2 and fork["number"] == 5
    assert fork["quote"] == second["quote"]
    assert fork["artifactVersionIds"]["quotation"] != second["artifactVersionIds"]["quotation"]
    assert checked(client.get(CASE + "/revisions/2")) == second
    draft = checked(client.get(CASE + "/revisions/5/reply-drafts/en-US"))
    assert draft["text"].startswith("Human edited") and draft["reviewStatus"] == "needs_review"
    checked(client.put(CASE + "/revisions/5/reply-drafts/en-US", json={"baseDraftVersion": 1, "text": "Continue editing after fork"}))
    assert client.post(CASE + "/revisions/1/restore", json={"baseRevision": 4}).status_code == 409
    assert checked(client.get(CASE + "/sop-status"))["productionRelease"]["status"] == "blocked"


def test_artifact_restoration_and_customer_source(client):
    payload = {"title": "New customer", "customer": "Example", "originalText": "Please quote 800 bags", "customerContext": {"channel": "amazon", "email": "buy@example.test", "website": "https://example.test", "simulation": True}}
    case = checked(client.post(BASE + "/inquiries", json=payload))
    assert checked(client.get(BASE + "/inquiries/" + case["id"]))["customerContext"]["channel"] == "amazon"
    assert client.patch(BASE + "/inquiries/" + case["id"], json={"metadataVersion": 1, "customerContext": {"website": "javascript:alert(1)"}}).status_code == 400
    a = checked(client.post(CASE + "/artifacts", json={"kind": "spec", "content": {"material": "cotton"}}))
    b = checked(client.post(CASE + f"/artifacts/{a['id']}/versions", json={"baseVersion": 1, "content": {"material": "polyester"}}))
    c = checked(client.post(CASE + f"/artifacts/{a['id']}/restore", json={"baseVersion": 2}))
    assert c["version"] == 3 and c["restoredFromId"] == a["id"] and c["basedOnId"] == b["id"]
    assert c["content"]["material"] == "cotton"
    checked(client.post(CASE + f"/artifacts/{c['id']}/versions", json={"baseVersion": 3, "content": {"material": "recycled cotton"}}))
    assert checked(client.get(CASE + f"/artifacts/{a['id']}"))["content"] == {"material": "cotton"}


def test_model_auth_failure_is_visible_and_demo_only(client, monkeypatch):
    import httpx
    import pytest
    from openai import AuthenticationError
    from app import agent
    def unavailable(_):
        raise AuthenticationError("provider secret must not be echoed", response=httpx.Response(401, request=httpx.Request("POST", "https://model.example")), body=None)
    monkeypatch.setattr(agent, "extract_with_model", unavailable)
    result = agent.understand_node({"text": "3000 backpacks"})
    assert result["extracted"]["quantity"] == 3000
    assert result["extractionWarnings"][0]["code"] == "MODEL_UNAVAILABLE"
    assert "secret" not in str(result)
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="鉴权失败"):
        agent.understand_node({"text": "3000 backpacks"})
