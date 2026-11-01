"""Explicit, append-only restoration of business nodes and their artifact snapshots."""
from copy import deepcopy

from sqlalchemy import text

from .core import create_item, decode, encode, fail, item_view, items, touch, uid
from .models import Item, now

NODE_FIELDS = {
    "requirements": ("requirements",), "risks": ("risks", "checks"),
    "quote": ("quote", "proposal"), "reply": ("replies",),
    "customer": ("requirements", "risks", "checks"), "sample": (), "order": (), "production": (),
}
NODE_ARTIFACTS = {
    "requirements": {"spec"}, "risks": set(), "reply": set(), "customer": set(),
    "quote": {"rfq", "comparison", "cost", "quotation"},
    "sample": {"sample"}, "order": {"pi"}, "production": {"production", "ta", "qc"},
}


def artifact_snapshot(db, case):
    latest = {}
    for row in items(db, "artifact", case_id=case.id):
        kind = decode(row.payload)["kind"]
        if kind not in latest or row.version > latest[kind].version:
            latest[kind] = row
    return {kind: row.id for kind, row in latest.items()}


def merge_generation(previous, generated, target):
    if not previous or not target:
        return generated
    result = deepcopy(previous)
    for field in NODE_FIELDS[target]:
        result[field] = generated[field]
    for key in ("number", "runId", "jobId", "createdAt", "changeSummary", "inputManifest", "ruleSetVersion"):
        if key in generated:
            result[key] = generated[key]
    result["parentRevision"] = previous["number"]
    result["generatedNode"] = target
    result.pop("restoredFromRevision", None)
    result.pop("restoredNode", None)
    refs = {r["sourceVersionId"]: r for r in [*previous.get("sourceRefs", []), *generated.get("sourceRefs", [])]}
    result["sourceRefs"] = list(refs.values())
    result["assetRefs"] = list(dict.fromkeys([*previous.get("assetRefs", []), *generated.get("assetRefs", [])]))
    for risk in generated.get("risks", []):
        if risk.get("category") == "MODEL_UNAVAILABLE" and not any(r.get("category") == "MODEL_UNAVAILABLE" for r in result.get("risks", [])):
            result["risks"].append(risk)
    return result


def historical_artifacts(db, case, source):
    if "artifactVersionIds" in source:
        return source["artifactVersionIds"]
    # Legacy revisions predate artifact manifests. Recover only artifacts from
    # recorded jobs up to that revision; never copy a later manual edit backwards.
    runs = {item_view(r).get("runId") for r in items(db, "revision", case_id=case.id) if r.version <= source["number"]}
    latest = {}
    for row in items(db, "artifact", case_id=case.id):
        value = item_view(row)
        kind = value["kind"]
        if value.get("runId") in runs and (kind not in latest or row.version > latest[kind].version):
            latest[kind] = row
    return {kind: row.id for kind, row in latest.items()}


def restore_revision(db, user, case, source_row, body):
    db.execute(text("BEGIN IMMEDIATE"))
    db.refresh(case)
    if body.get("baseRevision") != case.current_revision:
        fail("REVISION_CONFLICT", "当前版本已有更新，请刷新后恢复", 409)
    if case.active_run_id or decode(case.payload).get("pendingRunId"):
        fail("RUN_IN_PROGRESS", "请先完成或取消正在处理的任务", 409)
    if case.status in ("waiting", "done"):
        fail("INVALID_STATUS_TRANSITION", "请先恢复处理当前询盘", 409)
    if any(item_view(c).get("status") not in ("applied", "rejected", "cancelled") for c in items(db, "change_set", case_id=case.id)):
        fail("CHANGE_ACTIVATION_BLOCKED", "请先处理未关闭的变更，再恢复历史内容", 409)
    target = body.get("target", "all")
    if target not in ("all", "requirements", "risks", "quote", "reply"):
        fail("INVALID_INPUT", "不支持的恢复节点")
    source = item_view(source_row)
    current = next(item_view(r) for r in items(db, "revision", case_id=case.id) if r.version == case.current_revision)
    result = deepcopy(source if target == "all" else current)
    if target != "all":
        for field in NODE_FIELDS[target]:
            result[field] = deepcopy(source[field])
    number = case.current_revision + 1
    result.update(number=number, parentRevision=case.current_revision, restoredFromRevision=source["number"],
                  restoredNode=target, createdAt=now(), restoredBy=user.id, runId="", jobId=None,
                  changeSummary=[f"从 V{source['number']} 恢复{'全部节点' if target == 'all' else target}，创建可编辑草稿 V{number}"])
    for key in ("id", "importedBaseline", "generatedNode"):
        result.pop(key, None)
    if target in ("all", "quote"):
        result["proposal"] = {**result["proposal"], "version": number, "proposalId": uid("proposal"), "status": "proposed"}
        result["proposal"].pop("acceptanceEvidence", None)
    # Each new revision starts with fresh editable reply drafts, preserving edits
    # from the selected historical branch for reply/all, or current branch otherwise.
    reply_revision = source["number"] if target in ("all", "reply") else current["number"]
    for locale in ("en-US", "es-MX"):
        drafts = items(db, "draft", case_id=case.id, parent_id=f"{case.id}:{reply_revision}:{locale}")
        value = item_view(max(drafts, key=lambda d: d.version))["text"] if drafts else result["replies"][locale]
        result["replies"][locale] = value
        create_item(db, "draft", {"inquiryId": case.id, "revision": number, "locale": locale, "draftVersion": 1, "text": value, "reviewStatus": "needs_review", "updatedAt": now()}, case_id=case.id, parent_id=f"{case.id}:{number}:{locale}")
    source_artifacts = historical_artifacts(db, case, source)
    current_artifacts = artifact_snapshot(db, case)
    kinds = set(source_artifacts) | set(current_artifacts) if target == "all" else NODE_ARTIFACTS[target]
    restored = {}
    for kind in kinds:
        if kind not in source_artifacts and kind not in current_artifacts:
            continue
        present = kind in source_artifacts
        row = db.get(Item, source_artifacts.get(kind) or current_artifacts[kind])
        if not row or row.case_id != case.id or row.kind != "artifact":
            fail("NOT_FOUND", "历史成果原件不存在", 404)
        old = item_view(row)
        latest_id = current_artifacts.get(kind)
        version = db.get(Item, latest_id).version + 1 if latest_id else 1
        identifier = f"artifact_{case.id}_{kind}_v{version}"
        content = deepcopy(old["content"]) if present else {"missingFields": ["not_present_in_source_revision"], "pendingReconfirmation": True}
        content.update(status="draft", restoredFromArtifactId=row.id if present else None)
        for approval_field in ("released", "customerApproved"):
            if approval_field in content:
                content[approval_field] = False
        create_item(db, "artifact", {"kind": kind, "title": old["title"], "version": version, "content": content, "status": "draft", "basedOnId": latest_id, "restoredFromId": row.id, "restoredInRevision": number, "createdBy": user.id}, case_id=case.id, parent_id=kind, version=version, item_id=identifier)
        restored[kind] = identifier
    db.flush()
    # A full fork's manifest contains only that historical branch's artifacts.
    result["artifactVersionIds"] = restored if target == "all" else {**current_artifacts, **restored}
    if target != "all":
        result["sourceRefs"] = list({r["sourceVersionId"]: r for r in [*current.get("sourceRefs", []), *source.get("sourceRefs", [])]}.values())
    if target in ("all", "requirements", "quote"):
        for row in items(db, "approval", case_id=case.id):
            value = item_view(row)
            if value.get("decision") == "approved":
                value.update(decision="superseded", supersededByRevision=number)
                row.payload = encode(value)
    created = create_item(db, "revision", result, case_id=case.id, parent_id=case.id, version=number)
    case.current_revision = number
    case.status = "active"
    touch(case)
    create_item(db, "message", {"inquiryId": case.id, "role": "assistant", "text": result["changeSummary"][0] + "。历史保留；恢复的商业成果需重新批准。", "createdAt": now()}, case_id=case.id)
    db.commit()
    return item_view(created)
