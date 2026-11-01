"""Fixed incomplete-tote fixture; never fill gaps from the complete demo pack."""
from .core import decode, encode
from .domain import normalize_bom, normalize_spec
from .workbench import append_artifact, latest_artifacts, save_customer_profile


GAPS = [
    ("dimensions", "请确认袋子的长、宽、底宽及手提带尺寸。"),
    ("fabric", "请确认面料成分、克重及颜色，简洁自然只是风格方向。"),
    ("structure", "请确认袋型结构、内袋、里布和闭合方式。"),
    ("logo", "请提供 Logo 图稿，并确认印花工艺、位置、尺寸和颜色。"),
    ("packaging", "请确认单件包装、装箱要求、交期及运输条款。"),
]


def save_incomplete_node(db, case, run, job, node, label):
    data = decode(case.payload)
    current = latest_artifacts(db, case)
    questions = [question for _, question in GAPS]
    fields = {"product": "品牌帆布手提袋", "quantity": "5000", "destination": "Los Angeles, USA"}

    def save(kind, content, title):
        value = append_artifact(db, case, kind, {
            **content, "simulation": True, "generationMode": "local_mock", "status": "draft",
            "missingDetails": questions, "sourceRefs": [{"evidenceId": ref} for ref in data.get("demoEvidence", {}).values()],
        }, title=title, run_id=run.id, job_id=job.id)
        current[kind] = value
        return value

    # Re-running this fixed demo produces the same partial draft, never inferred specs.
    if node == "requirements" or not current.get("spec"):
        save("spec", normalize_spec({"fields": fields}), "客户需求与规格（待补充）")
    spec_id = current["spec"]["itemId"]
    if node == "inquiry":
        save_customer_profile(db, case, {**data.get("customerContext", {}), "company": data.get("customer"),
                                       "summary": "Maple Studio 模拟品牌客户，未进行外网背调。"}, run_id=run.id)
        save("inquiry_assessment", {"summary": "客户计划采购 5000 件品牌帆布手提袋，目的地洛杉矶；仅有风格方向，尚不具备准确报价条件。",
                                    "risks": questions, "missing": questions}, "客户与询盘评估")
    elif node == "requirements":
        save("bom", {"rows": normalize_bom([
            {"category": "material", "item": "帆布面料（成分、克重待确认）", "spec": None, "quantityPerPiece": None, "unit": None},
            {"category": "accessory", "item": "手提带及辅料（结构待确认）", "quantityPerPiece": None, "unit": None},
            {"category": "packaging", "item": "包装（待确认）", "quantityPerPiece": None, "unit": None},
        ])}, "产品 BOM（待补充）")
    elif node == "costing":
        save("quotation", {**fields, "quantity": 5000, "unitPriceUsd": None, "totalUsd": None,
                           "notes": "规格、供应商成本及商务条件未确认，暂不提供价格或交期。"}, "方案与报价（待补充）")
    elif node == "competitor":
        save("competitor_analysis", {"comparisons": [], "sources": [], "observations": [],
                                     "summary": "未提供对标商品或参考图，待客户补充后再比较。"}, "竞品分析（待补充）")
    elif node == "design":
        from .node_simulation_assets import save_design_image
        save_design_image(db, case, run, job, current["spec"], "us-tote")
    elif node == "risks":
        save("risk_review", {"risks": questions}, "风险与待确认项")
    elif node == "reply":
        save("customer_reply", {"replies": {
            "en-US": "Dear Emma,\n\nThank you for your inquiry for 5,000 canvas tote bags for your Los Angeles launch. Before quoting, could you share the bag and handle dimensions, fabric composition and weight, bag construction, logo artwork and print details, packaging, delivery date and shipping terms? We can prepare a proposal once these details are clear.\n\nBest regards,\nNavoWork",
            "zh-CN": "Emma 您好，感谢您咨询用于洛杉矶品牌活动的 5000 件帆布手提袋。为准备准确方案，请补充袋子及手提带尺寸、面料成分与克重、结构、Logo 图稿及印花要求，以及包装、交期和运输条款。确认这些信息后，我们再准备报价。",
        }}, "客户澄清回复草稿")
    elif node == "sample":
        save("sample", {"specVersionId": spec_id, "approval": {"decision": "pending", "evidenceId": None},
                        "notes": "产品细节及样品要求待确认，尚未打样。"}, "打样资料（待补充）")
    elif node == "order":
        save("order", {"specVersionId": spec_id, "po": {"quantity": 5000, "unitPriceUsd": None, "totalUsd": None},
                       "confirmations": {"buyer": {"confirmed": False}, "seller": {"confirmed": False}},
                       "notes": "尚未收到客户 PO，报价及付款条款待确认。"}, "订单资料（待补充）")
    elif node == "production":
        save("production", {"specVersionId": spec_id, "product": fields["product"], "quantity": 5000,
                            "productionDays": None, "packaging": None, "factoryConfirmation": {"confirmed": False},
                            "notes": "规格、样品及订单未确认，生产计划待补充。"}, "生产资料（待补充）")
    else:
        raise ValueError("Unknown incomplete simulation node")

    # Replace this node's previous warnings so repeated mock runs do not accumulate duplicates.
    data = decode(case.payload)
    warnings = data.setdefault("nodeWarnings", {})
    warnings[node] = [{"question": question, "field": field, "runId": run.id,
                       "skipped": True, "source": "local_mock"} for field, question in GAPS]
    case.payload = encode(data)
    return f"已使用本地 mock 完成「{label}」草稿，未调用模型 API。保留 {len(GAPS)} 项待确认信息，请查看节点黄色提醒。"
