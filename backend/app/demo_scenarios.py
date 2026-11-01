"""Synthetic roadshow inputs for real Agent chat, with bundled demo product images."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256

from .core import create_item, decode, encode, fail, item_view, items, now, uid
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
    themes = ["完整资料 · 六阶段演示", "信息不全 · 本地模拟缺项提醒", "功能设计 · 客户回复", "材料分析 · 设计方案", "通勤设计 · 报价建议"]
    return {"items": [{**{key: row[key] for key in ("id", "title", "customer", "quantity")}, "theme": theme,
                       **({"dataScope": "incomplete"} if row["id"] == "us-tote" else {})}
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
    if scenario_id == "de-backpack":
        fields.update(
            style="20 L everyday commuter backpack, adult use",
            dimensions="30 W x 45 H x 15 D cm; external finished size; tolerance +/- 0.5 cm",
            structure="one main compartment with two-way zip; one front zip pocket; two open mesh side pockets; one inner zip pocket",
            laptopSleeve="padded sleeve for 15.6 inch laptop, internal 28 W x 38 H cm, elastic securing strap",
            straps="two adjustable padded shoulder straps, 7 cm wide, adjustment 45-85 cm; reinforced top carry handle",
            lining="210D recycled polyester, 95 gsm, light grey; lining covers main and front compartments",
            filling="8 mm EPE shoulder/back padding; 5 mm EPE laptop protection; 1 mm PE bottom reinforcement",
            materialFinish="PU backing and PFAS-free water-repellent finish; light-rain resistant, not waterproof",
            zipper="#5 nylon coil two-way main zipper, single-way front/inner pocket zip; black metal pullers",
            buckle="black POM ladder-lock adjusters, 25 mm; no other metal hardware",
            webbing="25 mm black polyester, 1.2 mm thick; reinforced bartacks at all load-bearing points",
            logo="white embroidered NORDLICHT logo, 60 W x 25 H mm, centered on front pocket, top edge 40 mm below pocket zipper; +/- 2 mm position tolerance",
            label="30 x 15 mm NORDLICHT woven brand label inside main compartment; polyester care label at inner side seam; recycled paper hangtag",
            cartonSize="60 L x 40 W x 50 H cm, five-ply export carton; 20 pcs per carton; bags packed flat",
            cartonWeight="net 12.0 kg / gross 13.2 kg per carton; tolerance +/- 0.3 kg",
            shippingMarks="NORDLICHT / DE-BACKPACK / NAVY / QTY 20 PCS / CARTON 1-150 / MADE IN CHINA; no retail barcode required",
            tests="appearance and stitching; dimensions +/- 0.5 cm; 10 kg static load for 1 hour; 5000 zipper cycles; dry rub grade >=4 / wet rub >=3; EU REACH requirements as reference, no certification claim",
            sampleRequirement="one pre-production sample within 7 days; sample USD 50 + courier USD 25; mock approval evidence supplied separately",
        )
        s["dimensions"], s["logo"] = fields["dimensions"], fields["logo"]
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
    if scenario_id == "de-backpack":
        original += ("\nSynthetic buyer contact: Michael Weber, Purchasing Manager, Nordlicht Outdoor, "
            "Demo Harbour Street 18, 20457 Hamburg, Germany; buyer@de-backpack.example; "
            "https://de-backpack.example. All company/contact/approval/payment information is fictional demo input. "
            "The attached specification fixes dimensions, structure, lining, logo placement, packing and inspection. "
            "Use the supplied NORDLICHT wordmark artwork for this demo; no additional design decision is required.")
    s.update(fields=fields, computed=computed, sample=sample, order=order, validUntil=valid_until, originalText=original)
    return s


def creation_body(scenario_id: str, *, incomplete: bool = False):
    s = scenario_inputs(scenario_id)
    if incomplete:
        s["title"] = "美国 · 品牌帆布袋（信息待补充）"
        s["originalText"] = (
            "[SIMULATED INQUIRY / 路演模拟资料]\nFrom: Emma Carter, Maple Studio\n"
            "Hi, we are looking for 5,000 canvas tote bags for our brand launch in Los Angeles. "
            "We would like something simple, natural-looking and reusable, with our brand on it. "
            "We haven't decided the size, fabric weight, bag construction or printing details yet. "
            "Our artwork and reference photos are not ready. Could you help us work out the details "
            "and let us know what you need before quoting? Packaging, delivery date and shipping terms "
            "are still open.\nBest, Emma"
        )
    return dict(title=s["title"], customer=s["customer"], originalText=s["originalText"], destination=s["destination"],
                requestedLocales=["en-US", "es-MX"], customerContext=dict(channel="email", company=s["customer"],
                    country=s["country"], email=f"buyer@{s['id']}.example", website=f"https://{s['id']}.example",
                    business="Bags and lifestyle goods retailer (synthetic roadshow company)", simulation=True))


def seed_demo(db, case, scenario_id: str, *, full: bool = False, supplement: bool = False, incomplete: bool = False):
    s = scenario_inputs(scenario_id)
    refs = dict(decode(case.payload).get("demoEvidence", {})) if supplement else {}

    def evidence(key, role, title, content):
        if supplement and key in refs:
            return
        text = "路演模拟资料，不代表真实交易。\n" + (content if isinstance(content, str) else encode(content))
        row = create_item(db, "evidence", {"title": f"[演示] {title}", "sourceRole": role, "text": text,
                          "blobId": None, "sha256": sha256(text.encode()).hexdigest(),
                          "parseStatus": "parsed", "createdAt": now(), "simulation": True}, case_id=case.id, status="observed")
        db.flush()
        refs[key] = row.id

    if incomplete:
        # Deliberately exclude complete specs, prices, samples and hidden defaults.
        evidence("original", "customer_request", "客户原始邮件（信息不全）", decode(case.payload)["originalText"])
        evidence("brief", "customer_request", "品牌方向说明", "Maple Studio 品牌活动用帆布手提袋，5000 件，目的地 Los Angeles。偏好简洁、自然、可重复使用。尚未提供产品图、尺寸表、面料克重、结构和印花图稿。")
        case.payload = encode({**decode(case.payload), "demoScenarioId": scenario_id,
                              "demoDataScope": "incomplete", "demoEvidence": refs})
        return
    evidence("original", "customer_request", "客户原始邮件", s["originalText"])
    evidence("spec", "customer_approval" if full else "customer_request", "客户规格确认" if full else "客户参考规格", s["fields"])
    if scenario_id == "de-backpack":
        # A supplemental original adds complete details without rewriting existing user evidence.
        evidence("complete_spec", "customer_approval" if full else "customer_request", "完整规格与设计确认", {
            "specification": s["fields"], "contact": s["originalText"],
            "logoArtworkSvg": '<svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="25mm" viewBox="0 0 240 100"><path d="M20 75V25L60 75V25 M80 75V25L120 75V25" fill="none" stroke="white" stroke-width="7"/><text x="140" y="56" font-family="sans-serif" font-size="12" fill="white">NORDLICHT</text></svg>',
            "designStatus": "Complete synthetic design inputs for draft generation; all physical/customer approvals remain simulated and require the app's human review steps.",
        })
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
        document_title = f"[演示] {s['title']} · {title}"
        previous = [row for row in items(db, "resource", case_id=case.id) if decode(row.payload).get("title") == document_title] if supplement else []
        latest = max(previous, key=lambda row: row.version) if previous else None
        source_id = decode(latest.payload)["sourceId"] if latest else uid("knowledge")
        version = latest.version + 1 if latest else 1
        create_item(db, "resource", {"id": source_id, "sourceId": source_id, "version": version, "editVersion": 1, "updatedAt": now(),
                    "ownerId": case.owner_id, "kind": "knowledge", "title": document_title, "caseId": case.id,
                    "status": "published", "folder": "路演资料", "simulation": True, "content": encode(content),
                    "facts": {"fx": "7.20", "margin": "0.20", "quantity": s["quantity"]}}, case_id=case.id, status="published", item_id=f"{source_id}:v{version}", parent_id=source_id, version=version)
    case.payload = encode({**decode(case.payload), "demoScenarioId": scenario_id, "demoDataScope": "full" if full else "reference", "demoEvidence": refs,
                          **({"demoInputVersion": 2} if scenario_id == "de-backpack" else {})})


def complete_existing_backpack(db, case):
    data = decode(case.payload)
    if data.get("demoScenarioId") != "de-backpack" or data.get("demoInputVersion", 0) >= 2:
        return False
    if case.active_run_id:
        return False
    seed_demo(db, case, "de-backpack", full=True, supplement=True)
    from .core import touch
    touch(case)
    return True


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
    if payload.get("demoDataScope") in ("reference", "incomplete"):
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
