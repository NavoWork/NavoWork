from app.core import create_item, decode, encode
from app.db import SessionLocal
from app.models import Case, Run

BASE = "/api/v1/workspaces/ws_demo"
CASE = BASE + "/inquiries/inq_demo_bag"


def checked(response):
    assert response.status_code == 200, response.text
    return response.json()


def test_all_legacy_messages_remain_in_their_inquiry(client, other_client):
    before = checked(client.get(CASE + "/messages"))["items"]
    with SessionLocal() as db:
        for index in range(2):
            create_item(db, "message", {"inquiryId": "inq_demo_bag", "role": "user",
                        "text": f"旧对话消息 {index}", "conversationId": f"old_chat_{index}"}, case_id="inq_demo_bag")
        db.commit()
    after = checked(client.get(CASE + "/messages"))["items"]
    assert len(after) == len(before) + 2
    assert {m["id"] for m in before} <= {m["id"] for m in after}
    assert {"旧对话消息 0", "旧对话消息 1"} <= {m["text"] for m in after}
    # Obsolete filters cannot hide messages from the single inquiry chat.
    assert checked(client.get(CASE + "/messages?conversationId=default"))["items"] == after
    foreign = checked(client.post(BASE + "/inquiries", json={"title": "其他项目", "customer": "Other", "originalText": "100 bags"}))
    foreign_messages = checked(client.get(BASE + "/inquiries/" + foreign["id"] + "/messages"))["items"]
    assert not {m["id"] for m in after} & {m["id"] for m in foreign_messages}
    assert other_client.get(CASE + "/messages").status_code == 404


def test_removed_chat_management_does_not_cancel_current_task(client):
    run = checked(client.post(CASE + "/workbench/agent", json={"instruction": "检查询盘", "baseRevision": 0}))
    assert "conversationId" not in run
    assert checked(client.get(CASE))["latestRunId"] == run["id"]
    assert client.get(CASE + "/conversations").status_code == 404
    assert client.post(CASE + "/conversations", json={"cancelRunId": run["id"]}).status_code == 404
    assert checked(client.get(BASE + "/runs/" + run["id"]))["status"] == "queued"
    assert checked(client.get(CASE))["activeRunId"] == run["id"]
    assert any(m.get("runId") == run["id"] for m in checked(client.get(CASE + "/messages"))["items"])


def test_legacy_pending_run_can_continue_without_a_conversation(client):
    run = checked(client.post(CASE + "/runs", json={"baseRevision": 0, "instruction": "检查询盘"}))
    with SessionLocal() as db:
        row = db.get(Run, run["id"])
        row.status = "needs_input"
        row.payload = encode({**decode(row.payload), "conversationId": "old_chat", "clarification": {"questions": [{"id": "q1", "question": "尺寸？"}]}})
        case = db.get(Case, "inq_demo_bag")
        data = decode(case.payload)
        data.pop("latestRunId", None)
        case.active_run_id = None
        case.payload = encode({**data, "pendingRunId": run["id"]})
        db.commit()
    assert checked(client.get(CASE))["latestRunId"] == run["id"]
    resumed = checked(client.post(CASE + "/runs", json={"replyToRunId": run["id"], "baseRevision": 0, "answers": [{"questionId": "q1", "value": "20cm"}]}))
    assert resumed["id"] == run["id"]
    assert resumed["status"] == "queued"
    assert not checked(client.get(CASE)).get("pendingRunId")
    messages = checked(client.get(CASE + "/messages"))["items"]
    assert {"检查询盘", "20cm"} <= {m["text"] for m in messages}
