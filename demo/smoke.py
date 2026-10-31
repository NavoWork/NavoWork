"""One focused rehearsal in an isolated SQLite DB; never consumes the demo inbox."""
from pathlib import Path
import os
import tempfile

ROOT = Path(__file__).resolve().parents[1]
isolated = Path(tempfile.mkdtemp(prefix="navowork-demo-", dir=ROOT / "backend/data"))
os.environ.update(APP_ENV="demo", DATABASE_URL=f"sqlite:///{isolated.as_posix()}/smoke.sqlite3", STORAGE_ROOT=str(isolated / "storage"), MODEL_API_KEY="", MODEL_NAME="", DEMO_EMAIL="demo@navowork.local", DEMO_PASSWORD="ChangeMe123!")

from seed import seed
from advance import Demo, PREFIX
from app.main import app
from app.agent import build_graph
from app.worker import work_once
from fastapi.testclient import TestClient
from langgraph.checkpoint.sqlite import SqliteSaver


def main():
    with TestClient(app) as client, SqliteSaver.from_conn_string(str(isolated / "graph.sqlite3")) as checkpoint:
        seed("smoke")
        Demo.result(client.post("/api/v1/auth/session", json={"email": "demo@navowork.local", "password": "ChangeMe123!"}))
        graph = build_graph(checkpoint)
        case = Demo(client, "smoke", tick=lambda: work_once(graph))
        assert case.quote()["content"]["quote"]["unitPriceUsd"] == "8.69"
        assert case.change()["content"]["quote"]["unitPriceUsd"] == "9.21"
        assert case.order()["status"] == "blocked"
        blocked_pack = case.post("/production-packs", {"revision": case.get("")["currentRevision"]})
        assert client.post(case.path + f"/production-packs/{blocked_pack['id']}/release", json={}).status_code == 422
        assert len(case.check()["missing"]) == 6
        assert case.approve()["status"] == "ready_for_manual_release"
        assert case.release()["released"] is True
        quote = case.latest("quotation")
        exported = case.post(f"/artifacts/{quote['id']}/exports", {"format": "pdf"})
        assert client.get(exported["downloadUrl"]).content.startswith(b"%PDF")
        for key in ("de_b", "de_c", "mx", "uk"):
            state = Demo.result(client.get(f"{PREFIX}/inquiries/inq_smoke_{key}"))
            assert state["businessStatus"] == "todo" and not state["activeRunId"]
        print("PASS: quote -> change -> order -> blocked release -> approvals -> release -> PDF export. Isolated database:", isolated)


if __name__ == "__main__":
    main()
