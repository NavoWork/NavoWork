"""Editable next messages, grounded in the current case and the last agent reply."""
from __future__ import annotations

import hashlib
import re

from sqlalchemy import select

from .core import decode, encode, item_view, items
from .models import Run
from .settings_api import settings_values


INTENTS = {
    "requirements": ("需求整理", "requirements"), "clarify": ("补充资料", "requirements"),
    "reply": ("客户沟通", "requirements"), "rfq": ("供应商询价", "supplier-costing"),
    "cost": ("成本核算", "supplier-costing"), "quotation": ("客户报价", "quotation"),
    "sample": ("样品确认", "sample-feedback"), "order": ("订单核对", "po-check"),
    "production": ("生产准备", "production"), "qc": ("验货交付", "check-quality"),
    "change": ("变更复核", "changes"), "knowledge": ("资料检索", "knowledge-assets"),
}


def normalize_suggestions(values):
    if not isinstance(values, list):
        raise ValueError("建议须为列表")
    result, seen = [], set()
    for value in values[:5]:
        if not isinstance(value, dict):
            continue
        intent, title, message = value.get("intent"), value.get("title"), value.get("message")
        if intent not in INTENTS or not isinstance(title, str) or not isinstance(message, str):
            continue
        title, message = title.strip(), message.strip()
        if not title or not message or len(title) > 32 or len(message) > 400 or message in seen:
            continue
        # Suggestions are requests to prepare/review, never assertions of consent.
        if re.search(r"(?:自动|直接|立即|跳过).{0,8}(?:批准|放行|发送|核验到账)|我(?:已|确认).{0,8}(?:批准|付款|放行|签署)|(?:approve|release|send).{0,12}(?:automatically|immediately)", message, re.I):
            continue
        seen.add(message)
        result.append({"id": hashlib.sha256(message.encode()).hexdigest()[:12], "intent": intent,
                       "title": title, "message": message, "category": INTENTS[intent][0]})
    return result[:3]


def suggestion_context(db, case):
    artifacts = {}
    for row in items(db, "artifact", case_id=case.id):
        value = item_view(row)
        if value["kind"] not in artifacts or row.version > artifacts[value["kind"]]["version"]:
            artifacts[value["kind"]] = {**value, "version": row.version, "id": row.id}
    revisions = items(db, "revision", case_id=case.id)
    revision = next((item_view(r) for r in revisions if r.version == case.current_revision), {})
    messages = [item_view(r) for r in items(db, "message", case_id=case.id)]
    evidence = [item_view(r) for r in items(db, "evidence", case_id=case.id)]
    changes = [item_view(r) for r in items(db, "change_set", case_id=case.id) if item_view(r).get("status") not in ("applied", "cancelled", "rejected")]
    offers = [item_view(r) for r in items(db, "supplier_offer", case_id=case.id)]
    fingerprint = hashlib.sha256(encode({"revision": case.current_revision, "metadata": case.metadata_version,
        "settingsVersion": settings_values(db)["editVersion"],
        "artifacts": sorted(a["id"] for a in artifacts.values()), "messages": sorted(m["id"] for m in messages),
        "evidence": sorted(e["id"] for e in evidence), "offers": sorted(o["id"] for o in offers),
        "changes": [(c["id"], c["status"]) for c in changes]}).encode()).hexdigest()
    return {"artifacts": artifacts, "revision": revision, "messages": messages, "evidence": evidence,
            "changes": changes, "offers": offers, "fingerprint": fingerprint}


def next_messages(db, case):
    config = settings_values(db)
    if case.active_run_id or case.status in ("waiting", "done") or not config["agent"]["enabled"]:
        return {"items": [], "context": "", "revision": case.current_revision}
    context = suggestion_context(db, case)
    artifacts, revision = context["artifacts"], context["revision"]
    requirements = revision.get("requirements", {})
    enabled = {s["id"] for s in config["skills"] if s["enabled"]}
    latest_run = db.scalar(select(Run).where(Run.case_id == case.id).order_by(Run.created_at.desc(), Run.base_revision.desc()).limit(1))
    pending = decode(case.payload).get("pendingRunId")
    if pending:
        latest_run = db.get(Run, pending)
    candidates = []
    label = "从这条询盘开始"

    def add(intent, title, message):
        if INTENTS[intent][1] in enabled and (intent != "quotation" or "supplier-costing" in enabled):
            candidates.extend(normalize_suggestions([{"intent": intent, "title": title, "message": message}]))

    if latest_run and latest_run.status == "needs_input":
        questions = decode(latest_run.payload).get("clarification", {}).get("questions", [])
        fields = "\n".join(f"{q['question'][:100]}\n【请补充】" for q in questions[:3])
        add("clarify", "补充本次需要的信息", "关于刚才需要确认的信息，我补充如下：\n" + (fields or "【请补充资料或具体要求】"))
        add("knowledge", "先查已有资料", "请先查阅当前询盘原件与相关知识，补齐能够核实的信息；剩余缺项保持待确认，列出具体需要我提供的内容。")
        add("clarify", "先完成可做的部分", "这些信息暂时无法提供。请保留未知项，仅完成当前节点有依据的草稿，并列出仍需补充的资料，不推进后续节点。")
        return {"items": candidates, "context": "回应刚才的问题", "revision": case.current_revision}
    if latest_run and latest_run.status in ("failed", "cancelled"):
        add("requirements", "继续未完成的任务", "请先检查上次任务已经保存的结果，再继续未完成的部分：" + latest_run.instruction[:250])
        label = "继续未完成的工作"

    missing = requirements.get("missingFields") or artifacts.get("spec", {}).get("content", {}).get("missingFields") or []
    field_names = {"product": "产品类型", "quantity": "采购数量", "material": "面料", "dimensions": "尺寸", "packaging": "包装方式", "logo": "标识工艺", "destination": "目的地", "requested_arrival": "期望到货时间", "shippingSchedule": "运输安排"}
    missing_text = "、".join(field_names.get(str(f), str(f)) for f in missing[:4])
    product = str(requirements.get("requestedProduct") or decode(case.payload).get("title") or "当前产品")[:60]
    latest_reply = next((m["text"] for m in reversed(context["messages"]) if m.get("role") == "assistant"), "")
    quote_pending = artifacts.get("quotation", {}).get("content", {}).get("pendingReconfirmation")
    allowed = {"requirements", "clarify", "reply", "knowledge"}
    if context["changes"] or quote_pending:
        label = "先核对这次变更"
        allowed.add("change")
        add("change", "核对受影响的节点", "请根据刚才的回复和本次变更，逐项核对受影响的规格、成本与报价，列出已修订内容及仍需确认的条件，保留旧版本。")
        add("knowledge", "查找新版依据", "请在当前询盘原件及资产库中查找与这次变更对应的新规格和供应商报价，先核对款号与版本，再列出可用依据。")
        add("reply", "起草变更确认消息", "请围绕本次变更尚未确认的内容，起草一条简洁的确认消息，不代替客户接受新价格或交期。")
    elif not revision and not artifacts:
        add("requirements", "整理客户需求", f"请阅读{product}的原始来信，整理产品、数量、定制要求和交付目标，标出缺失信息，仅完成当前需求节点。")
        add("knowledge", "查找相关资料", "请根据这条询盘，在知识库和资产库中查找相关产品资料及规格规范，列出适用内容与来源，供我选择。")
        add("reply", "拟一条首次回复", "请根据客户原始询盘起草一条简洁的首次回复，说明已了解的需求并询问必要缺项，暂不承诺价格和交期。")
    else:
        allowed.add("rfq")
        if missing:
            label = "补齐当前需求"
            add("clarify", "补充需求信息", f"关于当前待确认的{missing_text}，我补充如下：\n【请填写实际要求】\n请更新需求，并保留其余未知项。")
            add("reply", "生成需求澄清消息", f"请针对尚未确认的{missing_text}，起草一条可发给客户的简洁澄清消息，避免重复询问已提供的信息。")
        if context["offers"] and not context["changes"]:
            allowed.add("cost")
        if "cost" in artifacts and not quote_pending:
            allowed.add("quotation")
        if "quotation" in artifacts and not quote_pending:
            allowed.add("sample")
        if "sample" in artifacts or "sample_feedback" in artifacts:
            allowed.add("order")
        if "pi" in artifacts or "po_check" in artifacts:
            allowed.add("production")
        if "production" in artifacts or "ta" in artifacts:
            allowed.add("qc")
        if "qc" in allowed:
            label = "准备验货与交付"
            add("qc", "整理验货与整改清单", "请根据最新规格、样品要求和现有验货反馈，整理验货清单、整改项及出货前待确认事项。")
        elif "production" in allowed:
            label = "核对生产前提"
            add("production", "检查生产准备条件", "请检查当前订单、最终样品、付款及供应商确认资料，列出放行缺口，并整理有依据的生产资料草稿。")
        elif "order" in allowed:
            label = "核对样品与订单"
            add("order", "核对客户 PO", "请查阅当前客户 PO，与最新规格、报价和样品要求逐项核对，保存差异报告；没有 PO 时先列出需要补充的文件。")
        elif "sample" in allowed:
            label = "跟进报价与样品"
            if re.search(r"样品|打样|sample", latest_reply, re.I):
                add("sample", "整理打样要求", "请根据刚才说明的样品要求和最新规格，整理打样指令与待确认事项，保留样品费用、交期及客户批准状态的未知项。")
            add("reply", "起草报价说明", "请基于当前报价草稿，起草一条简洁的客户说明，写清价格、条款、有效期和仍待确认的条件。")
            add("sample", "准备样品确认清单", "请根据当前规格和报价，准备样品确认清单；若已有客户样品反馈，先核对反馈中的修改要求。")
        elif "quotation" in allowed:
            label = "准备客户报价"
            add("quotation", "生成客户报价草稿", "请复核当前成本核算及供应商原件，按已选条件生成客户报价草稿，明确贸易条款、付款条件、有效期和未确认事项。")
        elif "cost" in allowed:
            label = "核对成本与报价"
            quantity = requirements.get("quantity")
            add("cost", "按当前条件核价", f"请核对已有供应商报价，按{'当前采购数量 ' + str(quantity) if quantity else '已确认采购数量'}及工作空间的汇率、毛利率核算成本，检查 MOQ 和费用口径；只生成成本表。")
        else:
            label = "补齐当前需求" if missing else "准备供应商询价"
            add("rfq", "准备供应商询价单", "请基于当前产品要求生成供应商询价草稿，列明规格、数量、包装和待确认项目，保留报价、MOQ及交期的待填项。")
            add("knowledge", "查找供应商报价原件", "请在资产库中查找匹配当前产品、数量及规格版本的供应商报价，列出可用文件与差异，先不要核价。")
        add("knowledge", "核对本轮资料依据", "请根据刚才的回复，列出本轮结论对应的原件与版本，并指出还缺哪些资料，不生成后续节点。")

    # Model-authored messages are reused only for the exact state they were based on.
    if latest_run and latest_run.status == "succeeded":
        stored = decode(latest_run.payload).get("messageSuggestions", {})
        if stored.get("fingerprint") == context["fingerprint"]:
            proposed = normalize_suggestions(stored.get("items", []))
            proposed = [s for s in proposed if s["intent"] in allowed and INTENTS[s["intent"]][1] in enabled
                        and (s["intent"] != "quotation" or "supplier-costing" in enabled)]
            candidates = [*proposed, *candidates]
    unique = {s["message"]: s for s in reversed(candidates)}
    result = list(reversed(list(unique.values())))[:3]
    return {"items": result, "context": label, "revision": case.current_revision}
