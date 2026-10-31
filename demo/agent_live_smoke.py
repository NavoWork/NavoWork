"""Small real-model acceptance against a temporary database, never the demo store.

Run with the project Python and PYTHONPATH=backend;agent-kit/src.
Reads model credentials from the ignored backend/.env and never prints them.
"""
from pathlib import Path
import json
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "agent-kit/src"))
from dev import local_env

os.environ.update(local_env())
if not os.getenv("MODEL_API_KEY") or not os.getenv("MODEL_NAME"):
    raise SystemExit("Configure MODEL_API_KEY and MODEL_NAME in backend/.env first")
directory = Path(tempfile.mkdtemp(prefix="agent-live-", dir=ROOT / "backend/data"))
os.environ.update(DATABASE_URL=f"sqlite:///{(directory / 'test.sqlite3').as_posix()}", STORAGE_ROOT=str(directory / "storage"), AGENT_FILE_TOOLS="0", APP_ENV="demo")

from fastapi.testclient import TestClient
from app.main import app
from app.core import create_item, store_blob
from app.db import SessionLocal
from app.models import now
from app.worker import work_once

BASE = "/api/v1/workspaces/ws_demo"
CASE = BASE + "/inquiries/inq_demo_bag"


def checked(response):
    assert response.status_code == 200, response.text[:500]
    return response.json()


def execute(client, instruction, revision):
    run = checked(client.post(CASE + "/runs", json={"action": "analyze", "instruction": instruction, "baseRevision": revision}))
    assert work_once(None)
    result = checked(client.get(BASE + "/runs/" + run["id"]))
    print(json.dumps({"status": result["status"], "revision": result.get("outputRevision"), "tools": [{"name": t["name"], "status": t["status"]} for t in result.get("toolCalls", [])], "loadedSkills": result.get("loadedSkills"), "error": result.get("error")}, ensure_ascii=False), flush=True)
    assert result["status"] == "succeeded", "Real agent did not complete"
    assert result["agentVerification"] == "live_model"
    return result


with TestClient(app) as client:
    checked(client.post("/api/v1/auth/session", json={"email": os.getenv("DEMO_EMAIL", "demo@navowork.local"), "password": os.getenv("DEMO_PASSWORD", "ChangeMe123!")}))
    with SessionLocal() as db:
        content = "Supplier Factory A, quote for 3000 backpacks to Hamburg. Base manufacturing CNY44.00 per piece, packaging CNY2.00 per piece, local charges CNY4.00 per piece. MOQ1000 pieces. Production lead time28 days after final approval and deposit; arrival not guaranteed."
        blob = store_blob(db, content.encode(), "Factory-A-current-quote.txt", "text/plain")
        create_item(db, "asset", {"id": "live_factory_a", "name": "Factory-A-current-quote.txt", "title": "Factory A 当前背包报价", "folder": "供应商报价", "space": "company", "version": 1, "sourceRole": "supplier_quote", "textContent": content, "blobId": blob.id, "mediaType": "text/plain", "size": blob.byte_size, "createdAt": now()}, item_id="live_factory_a:v1", parent_id="live_factory_a")
        create_item(db, "resource", {"id": "live_rule", "sourceId": "live_rule", "title": "背包核价规则", "kind": "knowledge", "status": "published", "version": 1, "content": "单件成本包括生产、包装与本地费用；报价按毛利率计算并上取到美分。生产期不等于到港期。", "updatedAt": now()}, item_id="live_rule:v1", parent_id="live_rule")
        db.commit()
    first = execute(client, "请整理当前询盘的需求与规格草稿。已知3000件背包，600D面料，目的地Hamburg；其他未知保持待确认。只完成需求节点，不生成回复或报价。", 0)
    artifacts = checked(client.get(CASE + "/artifacts"))["items"]
    assert {a["kind"] for a in artifacts} == {"spec"}, artifacts
    second = execute(client, "请从公司资产库找到Factory A当前背包报价，读取并关联为当前询盘原件，登记供应商报价。参考知识库核价规则，按数量3000、汇率7.20、毛利20%核价并生成客户报价草稿。FOB Ningbo，30%定金70%出货前，交期不承诺到港。不要推进打样或订单。", first["outputRevision"])
    revision = checked(client.get(CASE + f"/revisions/{second['outputRevision']}"))
    assert revision["quote"]["unitPriceMinor"] == 869, revision["quote"]
    assert revision["quote"]["goodsSubtotalMinor"] == 2607000
    artifacts = checked(client.get(CASE + "/artifacts"))["items"]
    assert not ({a["kind"] for a in artifacts} & {"sample", "pi", "production"})
    print(json.dumps({"result": "passed", "unitPriceUsd": "8.69", "goodsSubtotalUsd": "26070.00", "database": str(directory / "test.sqlite3")}, ensure_ascii=False))
