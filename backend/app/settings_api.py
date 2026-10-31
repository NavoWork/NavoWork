"""Workspace business defaults and the capabilities actually available to the agent."""
from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, urlunsplit

from .core import WORKSPACE_ID, create_item, decode, encode, fail, item_view, items
from .models import Item, now


SKILLS = [
    {"id": "requirements", "name": "询盘与需求", "description": "整理客户需求，标出缺项并起草澄清回复。", "tools": ["get_case_context", "read_evidence", "update_requirements", "update_risks", "update_customer_profile", "update_reply"]},
    {"id": "specification", "name": "产品规格", "description": "从已知要求编制规格书与供应商询价单。", "tools": ["save_artifact_draft"]},
    {"id": "supplier-costing", "name": "供应商与核价", "description": "读取知识库中的工厂资料，匹配需求并核价，保留版本依据。", "tools": ["register_knowledge_offer", "register_supplier_offer", "calculate_quote"]},
    {"id": "quotation", "name": "客户报价", "description": "按汇率与目标毛利生成报价草稿及商务条款。", "tools": ["calculate_quote", "save_artifact_draft"]},
    {"id": "changes", "name": "业务变更", "description": "分析数量、材料和包装变化，保留旧版并形成修订草稿。", "tools": ["analyze_change", "record_change_action", "save_artifact_draft"]},
    {"id": "sample-feedback", "name": "样品反馈", "description": "整理尺寸、工艺与包装意见，区分条件接受和最终确认。", "tools": ["load_skill", "review_order_skill", "save_artifact_draft"]},
    {"id": "po-check", "name": "订单核对", "description": "逐项核对 PO 与报价、规格的数量、金额及交付差异。", "tools": ["load_skill", "review_order_skill", "save_artifact_draft"]},
    {"id": "pi-prepare", "name": "PI 草稿", "description": "基于核对结果准备形式发票，保留待确认的商务条件。", "tools": ["load_skill", "review_order_skill", "save_artifact_draft"]},
    {"id": "production", "name": "生产准备", "description": "整理生产指令与排期，核对样品、订单及付款前提。", "tools": ["check_production_gate", "save_artifact_draft"]},
    {"id": "check-quality", "name": "验货与交付", "description": "形成验货清单、整改项与出货资料草稿。", "tools": ["save_artifact_draft"]},
    {"id": "knowledge-assets", "name": "知识与资产", "description": "检索业务知识、读取资料并将选定原件关联到当前询盘。", "tools": ["search_knowledge", "read_knowledge", "search_assets", "read_asset", "attach_asset", "save_knowledge_draft", "save_artifact_to_library"]},
]


def _key():
    return f"settings:{WORKSPACE_ID}"


def settings_values(db):
    row = db.get(Item, _key())
    stored = decode(row.payload) if row else {}
    capabilities = {item_view(r)["id"]: item_view(r).get("enabled", True) for r in items(db, "capability")}
    # Model credentials are process configuration; never return a key or URL credentials.
    endpoint = urlsplit(os.getenv("MODEL_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1")
    base_url = urlunsplit((endpoint.scheme, endpoint.netloc.rsplit("@", 1)[-1], endpoint.path, "", ""))
    switches = stored.get("skills", {})
    return {
        "editVersion": row.version if row else 0,
        "company": {"name": "NavoWork Trading", "contactEmail": "", "defaultCurrency": "USD", "defaultIncoterm": "FOB", "defaultPort": "Ningbo", "paymentTerms": "30% deposit, 70% before shipment", "replyLocale": "en-US", **stored.get("company", {})},
        "pricing": {"exchangeRate": "7.20", "targetMargin": "20", "quotationValidityDays": 14, **stored.get("pricing", {})},
        "agent": {"enabled": stored.get("agent", {}).get("enabled", True) and capabilities.get("agent", True),
                  "configured": bool(os.getenv("MODEL_API_KEY") and os.getenv("MODEL_NAME")),
                  "model": os.getenv("MODEL_NAME", ""), "baseUrl": base_url,
                  "fileToolsEnabled": os.getenv("AGENT_FILE_TOOLS", "0").lower() in ("1", "true", "yes"), "stepwise": True},
        "skills": [{**s, "enabled": switches.get(s["id"], True) and (capabilities.get("costing", True) if s["id"] in ("supplier-costing", "quotation") else True)} for s in SKILLS],
        "updatedAt": stored.get("updatedAt"),
    }


def skill_enabled(db, skill_id):
    value = settings_values(db)
    return value["agent"]["enabled"] and any(s["id"] == skill_id and s["enabled"] for s in value["skills"])


def _text(value, name, maximum=300, allow_empty=False):
    if not isinstance(value, str) or len(value) > maximum or (not allow_empty and not value.strip()):
        fail("INVALID_INPUT", f"{name} 格式不正确")
    return value.strip()


def settings_route(request, db, user, body):
    if request.method == "GET":
        return settings_values(db)
    if request.method != "PATCH":
        fail("NOT_FOUND", "接口不存在", 404)
    if user.role != "admin":
        fail("FORBIDDEN", "只有管理员可以修改工作空间设置", 403)
    if set(body) - {"company", "pricing", "agent", "skills", "editVersion"}:
        fail("INVALID_INPUT", "包含不支持的设置项")
    row = db.get(Item, _key())
    stored = decode(row.payload) if row else {}
    version = row.version if row else 0
    if "editVersion" in body and body["editVersion"] != version:
        fail("METADATA_CONFLICT", "设置已更新，请刷新后重试", 409)
    for section in ("company", "pricing", "agent"):
        if section in body and not isinstance(body[section], dict):
            fail("INVALID_INPUT", "设置项必须为对象")
    company = dict(stored.get("company", {}))
    for key, value in body.get("company", {}).items():
        if key not in ("name", "contactEmail", "defaultCurrency", "defaultIncoterm", "defaultPort", "paymentTerms", "replyLocale"):
            fail("INVALID_INPUT", "不支持的公司设置")
        company[key] = _text(value, key, allow_empty=key == "contactEmail")
    if company.get("defaultCurrency", "USD") != "USD":
        fail("INVALID_INPUT", "当前核价币种为 USD")
    if company.get("defaultIncoterm", "FOB") not in ("EXW", "FCA", "FOB", "CFR", "CIF", "DAP", "DDP"):
        fail("INVALID_INPUT", "请选择有效的贸易术语")
    if company.get("replyLocale", "en-US") not in ("en-US", "es-MX", "zh-CN"):
        fail("INVALID_INPUT", "不支持的回复语言")
    pricing = dict(stored.get("pricing", {}))
    for key, value in body.get("pricing", {}).items():
        if key not in ("exchangeRate", "targetMargin", "quotationValidityDays") or isinstance(value, bool):
            fail("INVALID_INPUT", "不支持的核价设置")
        try:
            numeric = Decimal(str(value))
            valid = numeric.is_finite() and (0 < numeric <= 10000 if key == "exchangeRate" else 0 <= numeric < 100 if key == "targetMargin" else 1 <= numeric <= 365 and numeric == numeric.to_integral_value())
            if not valid:
                raise ValueError()
        except (InvalidOperation, ValueError):
            fail("INVALID_INPUT", "汇率须大于零，毛利率须为 0–100%，有效期须为 1–365 天")
        pricing[key] = int(numeric) if key == "quotationValidityDays" else str(numeric)
    agent = dict(stored.get("agent", {}))
    for key, value in body.get("agent", {}).items():
        if key != "enabled" or type(value) is not bool:
            fail("INVALID_INPUT", "Agent 仅支持启用或停用设置")
        agent[key] = value
    switches = dict(stored.get("skills", {}))
    if "skills" in body:
        if not isinstance(body["skills"], list):
            fail("INVALID_INPUT", "技能设置须为列表")
        for skill in body["skills"]:
            if not isinstance(skill, dict) or set(skill) != {"id", "enabled"} or skill["id"] not in {s["id"] for s in SKILLS} or type(skill["enabled"]) is not bool:
                fail("INVALID_INPUT", "技能设置无效")
            switches[skill["id"]] = skill["enabled"]
    stored.update(company=company, pricing=pricing, agent=agent, skills=switches, updatedAt=now(), updatedBy=user.id)
    if row:
        row.payload, row.version, row.updated_at = encode(stored), version + 1, now()
    else:
        create_item(db, "workspace_settings", stored, item_id=_key(), version=1)
    create_item(db, "settings_event", {"actorId": user.id, "version": version + 1, "sections": [k for k in body if k != "editVersion"], "createdAt": now()})
    db.commit()
    return settings_values(db)
