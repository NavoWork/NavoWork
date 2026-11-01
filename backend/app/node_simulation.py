"""Local, deterministic node demos. This module never constructs a model client."""
import time
from decimal import Decimal

from sqlalchemy import text

from .core import create_item, decode, encode, now
from .db import SessionLocal
from .demo_scenarios import scenario_inputs
from .domain import calculate_cost, normalize_bom, normalize_spec
from .models import Case, Job, Run, WorkItem
from .node_simulation_assets import demo_node_data, save_competitors, save_design_image
from .workbench import append_artifact, finalize_agent_run, latest_artifacts, save_customer_profile

PHASES = ("understanding", "retrieving", "calculating", "composing", "validating", "committing")
PHASE_SECONDS = 0.7
LABELS = {"inquiry": "客户与询盘", "requirements": "客户需求与规格", "competitor": "竞品分析", "design": "产品设计图", "costing": "方案与报价", "risks": "风险与待确认项", "reply": "双语回复", "sample": "打样资料", "order": "订单与合同", "production": "生产资料"}


def active_context(db, item_id, generation):
    work = db.get(WorkItem, item_id)
    run = db.get(Run, work.run_id) if work else None
    if not work or work.lease_generation != generation or work.status != "running" or not run or run.status != "running":
        return None
    case = db.get(Case, run.case_id)
    if case.active_run_id != run.id:
        return None
    return case, run, db.get(Job, run.job_id), work


def save_simulated_node(db, case, run, job):
    node = decode(job.payload)["simulationNode"]
    data = decode(case.payload)
    if "editedText" in decode(job.payload):
        from .node_simulation_edits import save_edited_node
        return save_edited_node(db, case, run, job, node, LABELS[node])
    if data.get("demoDataScope") == "incomplete":
        from .node_simulation_incomplete import save_incomplete_node
        return save_incomplete_node(db, case, run, job, node, LABELS[node])
    scenario_id = data.get("demoScenarioId")
    s = scenario_inputs(scenario_id or "de-backpack")
    current = latest_artifacts(db, case)
    fields = {**s["fields"], **{k: v for k, v in current.get("spec", {}).get("content", {}).get("fields", {}).items() if v}}
    if not scenario_id:
        fields["product"] = current.get("spec", {}).get("content", {}).get("fields", {}).get("product") or data.get("title") or "演示产品"
        fields["destination"] = data.get("destination") or fields["destination"]
    try:
        quantity = max(1, int(str(fields["quantity"]).replace(",", "")))
    except (ValueError, TypeError):
        quantity = s["quantity"]
    fields["quantity"] = str(quantity)

    def save(kind, content, title):
        value = append_artifact(db, case, kind, {**content, "simulation": True, "generationMode": "local_mock", "status": "draft"},
            title=title, run_id=run.id, job_id=job.id)
        current[kind] = value
        return value

    def spec():
        if node == "requirements" or not current.get("spec"):
            save("spec", normalize_spec({"fields": fields}), "客户需求与规格")

    def quotation():
        lines = [{"category": category, "label": label, "amountCny": s[key], "scope": "per_unit"}
                 for category, label, key in (("material", "模拟工厂成本", "base"), ("packaging", "包装", "packaging"), ("domesticFreight", "国内运输", "local"))]
        cost = calculate_cost(lines, exchange_rate="7.20", margin="0.20", quantity=quantity)
        cost_row = save("cost", {**cost, "supplier": "Demo Factory A", "lines": lines}, "成本核算")
        save("comparison", {"offers": [{"supplier": f"Demo Factory {label}", "baseCny": str(Decimal(s["base"]) + extra), "leadDays": s["days"] + extra} for label, extra in (("A", 0), ("B", 3))], "recommendation": "工厂 A 成本更低，作为演示报价方案"}, "供应商比价")
        save("quotation", {**cost, "product": fields["product"], "quantity": quantity, "currency": "USD", "incoterm": fields["incoterm"],
            "incotermsVersion": "2020", "namedPlace": fields["namedPlace"], "paymentTerms": fields["paymentTerms"], "validUntil": s["validUntil"],
            "moq": 500, "sampleTime": "7 days", "productionDays": s["days"], "productionTime": fields["delivery"],
            "costVersionId": cost_row["itemId"], "exclusions": ["international freight", "insurance", "import duty"],
            "notes": "模拟报价草稿，按本地案例成本计算，待人工审核。"}, "方案与报价")

    warnings = list(dict.fromkeys(w["question"] for values in data.get("nodeWarnings", {}).values() for w in values))
    if node == "inquiry":
        save_customer_profile(db, case, {**data.get("customerContext", {}), "company": data.get("customer"), "summary": "模拟客户背景，基于当前询盘资料整理"}, run_id=run.id)
        save("inquiry_assessment", {"summary": f"{data.get('customer', '客户')}询购{quantity}件{fields['product']}，拟按{fields['incoterm']} {fields['namedPlace']}交付。", "risks": warnings, "missing": []}, "客户与询盘")
    elif node == "requirements":
        spec()
        save("bom", {"rows": normalize_bom([{"category": "material", "item": fields["fabric"], "spec": fields["dimensions"], "quantityPerPiece": "1", "unit": "set"},
            {"category": "accessory", "item": fields["zipper"], "quantityPerPiece": "1", "unit": "set"},
            {"category": "packaging", "item": fields["packaging"], "quantityPerPiece": "1", "unit": "set"}])}, "产品 BOM")
    elif node == "costing":
        spec()
        quotation()
    elif node == "competitor":
        spec()
        save_competitors(db, case, run, current, scenario_id or "de-backpack")
    elif node == "design":
        spec()
        save_design_image(db, case, run, job, current["spec"], scenario_id or "de-backpack")
    elif node == "risks":
        save("risk_review", {"risks": warnings or ["交期从样品确认及收到定金起算，需确认起算时间。", "正式报价不含国际运费、保险和进口税费。", "生产前需完成人工规格、样品和订单确认。"]}, "风险与待确认项")
    elif node == "reply":
        quote = current.get("quotation", {}).get("content", {})
        price = f"USD {quote['unitPriceUsd']} per unit, {quote.get('incoterm', 'FOB')} {quote.get('namedPlace', 'Ningbo')}" if quote.get("unitPriceUsd") else "pricing to be confirmed after specification review"
        save("customer_reply", {"replies": {"en-US": f"Dear {data.get('customer', 'Customer')},\n\nThank you for your inquiry for {quantity:,} {fields['product']}. Our draft proposal is {price}. Production takes {s['days']} days after sample approval and deposit receipt. Please confirm the specification and outstanding details before we proceed.\n\nBest regards,\nNavoWork",
            "es-MX": f"Estimado cliente:\n\nGracias por su consulta de {quantity:,} unidades. Nuestra propuesta preliminar: {price}. El plazo de producción es de {s['days']} días después de aprobar la muestra y recibir el anticipo. Confirme las especificaciones y los detalles pendientes.\n\nSaludos cordiales,\nNavoWork"}}, "双语回复草稿")
    elif node == "sample":
        spec()
        save("sample", {**s["sample"], "specVersionId": current["spec"]["itemId"], "approval": {"decision": "pending", "evidenceId": None}}, "样品记录")
    elif node == "order":
        spec()
        if not current.get("quotation"):
            quotation()
        quote = current["quotation"]["content"]
        total = Decimal(str(quote["unitPriceUsd"])) * quantity
        deposit = (total * Decimal("0.30")).quantize(Decimal("0.01"))
        schedule = [{**item, "amountUsd": str(amount)} for item, amount in zip(s["order"]["paymentSchedule"], (deposit, total - deposit))]
        order = save("order", {**s["order"], "po": {**s["order"]["po"], "quantity": quantity, "unitPriceUsd": quote["unitPriceUsd"], "totalUsd": str(total)}, "paymentSchedule": schedule,
            "quotationVersionId": current["quotation"]["itemId"], "specVersionId": current["spec"]["itemId"],
            "confirmations": {"buyer": {"confirmed": False}, "seller": {"confirmed": False}}}, "订单与合同")
        save("payment", {"schedule": schedule, "orderVersionId": order["itemId"], "verification": {"verified": False}}, "付款计划")
    elif node == "production":
        spec()
        save("production", {"specVersionId": current["spec"]["itemId"], "sampleVersionId": current.get("sample", {}).get("itemId"), "orderVersionId": current.get("order", {}).get("itemId"),
            "product": fields["product"], "quantity": quantity, "productionDays": s["days"], "packaging": fields["packaging"], "shippingMarks": fields.get("shippingMarks", "按客户确认唛头"),
            "qcStandard": fields["inspection"], "factoryConfirmation": {"confirmed": False}}, "生产资料")
        _, tasks = demo_node_data(scenario_id or "de-backpack")
        save("ta", {"tasks": [{"day": round(task["dayRatio"] * s["days"]), "task": task["task"], "owner": task["owner"]} for task in tasks]}, "T&A 计划")
        save("qc", {"standard": fields["inspection"], "checks": ["尺寸与外观", "面料及辅料", "Logo位置", "车缝与承重", "包装及唛头"], "requirements": fields["tests"]}, "QC 检查表")
    else:
        raise ValueError("Unknown simulation node")
    return f"已用模拟资料保存「{LABELS[node]}」草稿，可在画板节点查看。" + ("原有缺项仍保留待确认警告。" if warnings else "")


def execute_simulation_work(item_id, generation):
    for index, phase in enumerate(PHASES):
        with SessionLocal() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            context = active_context(db, item_id, generation)
            if not context:
                return
            case, run, job, work = context
            run.phase = phase
            run.last_seq += 1
            run.payload = encode({**decode(run.payload), "completedPhases": list(PHASES[:index])})
            create_item(db, "run_event", {"runId": run.id, "inquiryId": case.id, "seq": run.last_seq, "type": "run.running", "payload": {"phase": phase, "executionMode": "simulation"}, "createdAt": now()}, case_id=case.id, parent_id=run.id)
            db.commit()
        time.sleep(PHASE_SECONDS)
    with SessionLocal() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        context = active_context(db, item_id, generation)
        if not context:
            return
        case, run, job, work = context
        summary = save_simulated_node(db, case, run, job)
        run.payload = encode({**decode(run.payload), "completedPhases": list(PHASES), "agentVerification": {"liveExecuted": False, "mode": "local_mock", "modelApiCalled": False}})
        finalize_agent_run(db, case, run, job, summary, node=decode(job.payload)["simulationNode"], artifacts_changed=True)
        work.status = "done"
        db.commit()
