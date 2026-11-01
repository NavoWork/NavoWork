"""Synthetic roadshow inputs for real Agent chat, with bundled demo product images."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256

from .core import create_item, decode, encode, fail, item_view, now, uid
from .domain import calculate_cost
from .workbench import _approval_for, latest_artifacts, latest_customer_profile, stage_state


SCENARIOS = [
    dict(id="de-backpack", title="德国 · 再生面料背包", customer="Nordlicht Outdoor", contact="Michael Weber", country="Germany", destination="Hamburg, Germany", product="recycled polyester backpack", quantity=3000, dimensions="30 x 45 x 15 cm", fabric="600D recycled polyester, 300 gsm", logo="embroidered logo, 60 x 25 mm", color="navy blue", base="44", packaging="2", local="4", days=28, theme="供应商比价 · 标准订单"),
    dict(id="us-tote", title="美国 · 品牌帆布袋", customer="Maple Studio", contact="Emma Carter", country="USA", destination="Los Angeles, USA", product="cotton canvas tote bag", quantity=5000, dimensions="38 x 42 x 10 cm", fabric="12 oz cotton canvas", logo="one-color screen print, 120 x 80 mm", color="natural", base="18", packaging="1", local="2", days=21, theme="大批量定制 · 印花确认"),
    dict(id="uk-duffel", title="英国 · 健身旅行包", customer="Harbor Fitness", contact="Oliver Reed", country="UK", destination="London, UK", product="sports duffel bag", quantity=2000, dimensions="50 x 28 x 25 cm", fabric="900D polyester with PU backing", logo="woven patch, 70 x 35 mm", color="black", base="60", packaging="3", local="5", days=30, theme="功能规格 · 产前样确认"),
    dict(id="jp-cooler", title="日本 · 保温午餐包", customer="Hikari Living", contact="Yuki Tanaka", country="Japan", destination="Yokohama, Japan", product="insulated lunch bag", quantity=4000, dimensions="24 x 18 x 20 cm", fabric="600D polyester with PEVA lining and 5 mm EPE insulation", logo="heat transfer, 50 x 20 mm", color="light grey", base="26", packaging="2", local="3", days=25, theme="材料分层 · 品质检查"),
    dict(id="au-laptop", title="澳洲 · 通勤电脑包", customer="Southern Desk", contact="Chloe Wilson", country="Australia", destination="Sydney, Australia", product="15.6 inch laptop shoulder bag", quantity=1500, dimensions="40 x 30 x 8 cm", fabric="420D nylon with 8 mm foam laptop padding", logo="woven label, 40 x 15 mm", color="charcoal", base="72", packaging="3", local="5", days=32, theme="小批量采购 · 生产放行"),
]


def catalog():
    themes = ["需求分析 · 供应商比价", "品牌定制 · 产品设计", "功能设计 · 客户回复", "材料分析 · 设计方案", "通勤设计 · 报价建议"]
    return {"items": [{**{key: row[key] for key in ("id", "title", "customer", "quantity")}, "theme": theme}
                      for row, theme in zip(SCENARIOS, themes)]}


def scenario_inputs(scenario_id: str):
    source = next((row for row in SCENARIOS if row["id"] == scenario_id), None)
    if not source:
        fail("INVALID_INPUT", "演示询盘不存在，请重新选择", 400)
    s = dict(source)
    valid_until = (date.today() + timedelta(days=30)).isoformat()
    delivery = f"{s['days']} days after sample approval and deposit receipt; FOB Ningbo handover, not arrival"
    terms = "30% deposit, 70% before shipment"
    fields = dict(product=s["product"], quantity=str(s["quantity"]), dimensions=s["dimensions"], fabric=s["fabric"],
                  color=s["color"], logo=s["logo"], packaging="individual recycled polybag + hangtag; 20 pcs per export carton",
                  inspection="AQL 2.5 major / 4.0 minor, pre-shipment inspection", destination=s["destination"],
                  incoterm="FOB", incotermsVersion="2020", namedPlace="Ningbo", paymentTerms=terms, delivery=delivery,
                  zipper="#5 nylon coil zipper", webbing="25 mm polyester", tests="appearance, dimensions, stitching, load test",
                  sampleRequirement="one pre-production sample; 7 days", cartonQty="20")
    computed = calculate_cost([
        {"category": "material", "label": "factory base", "amountCny": s["base"], "scope": "per_unit"},
        {"category": "packaging", "label": "packaging", "amountCny": s["packaging"], "scope": "per_unit"},
        {"category": "domesticFreight", "label": "local transport", "amountCny": s["local"], "scope": "per_unit"},
    ], exchange_rate="7.20", margin="0.20", quantity=s["quantity"])
    total = Decimal(computed["totalUsd"])
    deposit = (total * Decimal("0.30")).quantize(Decimal("0.01"))
    schedule = [dict(milestone="deposit", ratio="0.30", amountUsd=str(deposit), due="before production"),
                dict(milestone="balance", ratio="0.70", amountUsd=str(total - deposit), due="before shipment")]
    code = s["id"].upper()
    order = dict(po=dict(number=f"DEMO-PO-{code}", buyer=s["customer"], quantity=s["quantity"], unitPriceUsd=computed["unitPriceUsd"],
                         totalUsd=str(total), incoterm="FOB", namedPlace="Ningbo", paymentTerms=terms,
                         destination=s["destination"], deliveryDate=delivery),
                 pi=dict(number=f"DEMO-PI-{code}", seller="Navo Demo Trading", bank="Demo Bank (simulation only)", origin="China"),
                 paymentSchedule=schedule, documents=["commercial invoice", "packing list", "bill of lading"])
    sample = dict(type="pre_production", round=1, sampleRef=f"DEMO-SMP-{code}", feeUsd="50.00", courierUsd="25.00",
                  checks={key: "passed" for key in ("appearance", "dimensions", "function", "workmanship", "packaging")},
                  feedback="Customer approved the sample against the agreed specification.", sealedSample={"location": "demo sample room", "ref": f"DEMO-SMP-{code}"})
    original = (f"[SIMULATED INQUIRY / 路演模拟资料]\nFrom: {s['contact']}, {s['customer']}\n"
                f"Please quote {s['quantity']:,} {s['product']}, {s['dimensions']}, {s['fabric']}, {s['color']}, "
                f"with {s['logo']}. FOB Ningbo (Incoterms 2020), destination {s['destination']}. "
                f"Payment: {terms}. Production: {delivery}. Please review our reference specifications and factory offers.")
    s.update(fields=fields, computed=computed, sample=sample, order=order, validUntil=valid_until, originalText=original)
    return s


def creation_body(scenario_id: str):
    s = scenario_inputs(scenario_id)
    return dict(title=s["title"], customer=s["customer"], originalText=s["originalText"], destination=s["destination"],
                requestedLocales=["en-US", "es-MX"], customerContext=dict(channel="email", company=s["customer"],
                    country=s["country"], email=f"buyer@{s['id']}.example", website=f"https://{s['id']}.example",
                    business="Bags and lifestyle goods retailer (synthetic roadshow company)", simulation=True))


def seed_demo(db, case, scenario_id: str, *, full: bool = False):
    s = scenario_inputs(scenario_id)
    refs = {}

    def evidence(key, role, title, content):
        text = "路演模拟资料，不代表真实交易。\n" + (content if isinstance(content, str) else encode(content))
        row = create_item(db, "evidence", {"title": f"[演示] {title}", "sourceRole": role, "text": text,
                          "blobId": None, "sha256": sha256(text.encode()).hexdigest(),
                          "parseStatus": "parsed", "createdAt": now(), "simulation": True}, case_id=case.id, status="observed")
        db.flush()
        refs[key] = row.id

    evidence("original", "customer_request", "客户原始邮件", s["originalText"])
    evidence("spec", "customer_approval" if full else "customer_request", "客户规格确认" if full else "客户参考规格", s["fields"])
    offers = []
    for i, label in enumerate(("A", "B")):
        offer = dict(supplier=f"Demo Factory {label} · {s['id']}", baseCny=str(Decimal(s["base"]) + i * 3),
                     packagingCny=s["packaging"], localCny=s["local"], includesPackaging=False,
                     moq=500, leadDays=s["days"] + i * 3, validUntil=s["validUntil"], incoterm="FOB", namedPlace="Ningbo",
                     paymentTerms=s["fields"]["paymentTerms"], scope="per_unit", currency="CNY",
                     notes="Base includes all material, logo, labor, normal waste and inspection; packaging/local listed separately. No other charges. Both factories meet the specification.")
        evidence(f"supplier{label}", "supplier_quote", f"工厂 {label} 报价单", offer)
        offers.append({**offer, "evidenceId": refs[f"supplier{label}"]})
    if full:
        evidence("sample", "customer_approval", "样品检查与客户批准", s["sample"])
        evidence("po", "customer_po", "采购订单与 PI 资料", s["order"])
        evidence("buyer", "customer_approval", "买方订单确认", {"confirmation": "Buyer accepts this PO and PI", **s["order"]})
        evidence("seller", "internal_note", "卖方订单确认", {"confirmation": "Seller accepts this PO and PI", **s["order"]})
        evidence("payment", "payment_receipt", "模拟定金凭据", {"simulation": True, "po": s["order"]["po"]["number"], "amountUsd": s["order"]["paymentSchedule"][0]["amountUsd"], "currency": "USD", "status": "simulated receipt for human review; not verified", "schedule": s["order"]["paymentSchedule"]})
        evidence("production", "supplier_confirmation", "工厂生产条件确认", {"supplier": offers[0]["supplier"], "productionDays": s["days"], "specification": s["fields"], "sampleRef": s["sample"]["sampleRef"], "po": s["order"]["po"]["number"], "confirmation": "Materials, capacity and agreed FOB lead time confirmed for simulation."})
    packs = [
        ("规格与 BOM 资料", {"specification": s["fields"], "sourceId": refs["spec"], "bom": [dict(category="material", item=s["fabric"], spec=s["dimensions"], quantityPerPiece="1", unit="set", sourceId=refs["spec"]) ]}),
        ("采购与核价依据", {"fx": "7.20", "margin": "0.20", "quantity": s["quantity"], "offers": offers, "selection": "Factory A meets all requirements and has the lowest cost; Factory A is a candidate for quotation; final selection requires review.", "pricing": "Margin is gross margin: total cost / 7.20 / (1 - 0.20). Round unit USD to 2 decimals, then multiply quantity. Costs already include material, labor, waste, logo and inspection; do not duplicate BOM costs.", "quotation": {"validUntil": s["validUntil"], "moq": 500, "sampleTime": "7 days", "productionDays": s["days"], "exclusions": ["international freight", "insurance", "import duty"]}}),
        ("样品、订单与生产资料", {"sample": s["sample"], "order": s["order"], "evidenceRefs": refs, "qcStandard": s["fields"]["inspection"], "ta": [{"day": 0, "task": "verify approved spec, sample and deposit", "owner": "merchandiser"}, {"day": 7, "task": "material inspection and cutting", "owner": "factory"}, {"day": s["days"] - 3, "task": "pre-shipment inspection", "owner": "QC"}, {"day": s["days"], "task": "FOB Ningbo handover", "owner": "logistics"}]})
    ]
    if not full:
        packs = packs[:2]
    for title, content in packs:
        source_id = uid("knowledge")
        create_item(db, "resource", {"id": source_id, "sourceId": source_id, "version": 1, "editVersion": 1, "updatedAt": now(),
                    "ownerId": case.owner_id, "kind": "knowledge", "title": f"[演示] {s['title']} · {title}", "caseId": case.id,
                    "status": "published", "folder": "路演资料", "simulation": True, "content": encode(content),
                    "facts": {"fx": "7.20", "margin": "0.20", "quantity": s["quantity"]}}, case_id=case.id, status="published", item_id=f"{source_id}:v1", parent_id=source_id)
    case.payload = encode({**decode(case.payload), "demoScenarioId": scenario_id, "demoDataScope": "full" if full else "reference", "demoEvidence": refs})


PROMPTS = {
    "inquiry": "请读取本询盘的演示资料包，整理客户背景和询盘摘要，标明客户为模拟数据，无需外网背调。保存客户档案和询盘评估。",
    "requirements": "请依据项目资料中的完整规格整理客户需求与规格，生成 Tech Pack 和 BOM，保存成果供我确认。",
    "costing": "请读取两家供应商报价并登记比价，按资料约定选择工厂 A，使用已确认汇率 7.20、毛利率 20% 和询盘数量调用核价工具，再生成完整客户报价。不要重复计入 BOM 成本。",
    "sample": "请读取演示样品检查与客户批准资料，登记产前样和各项检查、封样信息，绑定当前规格版本，保存后交由我确认。",
    "order": "请读取演示 PO、PI 和付款凭据，核对当前报价及规格，登记完整订单和 30%/70% 付款计划。买卖双方确认与定金核验由我操作。",
    "production": "请依据已确认的规格、报价、样品、订单和演示生产资料，生成生产包、T&A 和 QC 检查表，保存后交由我确认工厂条件并放行。",
}

STEPS = [
    ("requirements", ["spec", "bom"], [("customer_spec_approval", "spec", "spec", "确认客户规格")]),
    ("costing", ["cost", "quotation"], [("commercial_quotation_approval", "quotation", "", "审核客户报价")]),
    ("sample", ["sample"], [("sample_approval", "sample", "sample", "确认产前样")]),
    ("order", ["order", "payment"], [("order_buyer_confirmation", "order", "buyer", "确认买方订单"), ("order_seller_confirmation", "order", "seller", "确认卖方订单"), ("payment_verification", "payment", "payment", "核验模拟定金")]),
    ("production", ["production", "ta", "qc"], [("supplier_production_confirmation", "production", "production", "确认工厂生产条件"), ("production_release", "production", "", "放行演示生产包")]),
]


def demo_guide(db, case):
    payload = decode(case.payload)
    if not payload.get("demoScenarioId"):
        fail("NOT_FOUND", "该询盘不是演示询盘", 404)
    if payload.get("demoDataScope") == "reference":
        return {"kind": "chat", "node": None, "title": "选择你想展示的 AI 能力"}
    artifacts = latest_artifacts(db, case)
    stages = {s["key"]: s for s in stage_state(db, case)}

    def run(node):
        return {"kind": "run", "node": node, "title": stages[node]["title"], "prompt": PROMPTS[node]}

    if not latest_customer_profile(db, case) or not artifacts.get("inquiry_assessment"):
        return run("inquiry")
    for node, required, approvals in STEPS:
        human_pending = {"买方确认", "卖方确认", "付款核验", "供应商生产条件尚未确认"}
        missing_inputs = [m for m in stages[node]["missing"] if m not in human_pending]
        if any(not artifacts.get(kind) for kind in required) or missing_inputs:
            return run(node)
        for scope, kind, evidence_key, title in approvals:
            target = artifacts[kind]
            if _approval_for(db, case, scope, target):
                continue
            from .models import Item
            ref = payload.get("demoEvidence", {}).get(evidence_key)
            evidence = db.get(Item, ref) if ref else None
            return {"kind": "approval", "node": node, "title": title, "scope": scope, "targetVersionId": target["itemId"],
                    "evidenceRefs": [ref] if ref else [], "evidence": item_view(evidence) if evidence else None,
                    "content": target["content"], "version": target["version"]}
    return {"kind": "done", "node": "production", "title": "六阶段已完成 · 演示生产包已放行"}
