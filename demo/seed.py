"""Add a reproducible demo batch without resetting existing work.

Run from repository root: backend/.venv/Scripts/python.exe demo/seed.py
Use --batch rehearsal2 for a fresh set of cases, never an in-place reset.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dev import local_env
os.environ.update(local_env())
os.chdir(ROOT / "backend")
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select
from app.core import WORKSPACE_ID, bootstrap, create_item, decode, encode, item_view, store_blob
from app.db import Base, SessionLocal, engine
from app.models import Case, CaseAccess, Item, Job, Run, User, now
from app.agent import draft_node, price_quote
from app.worker import build_revision
from customer_profiles import customer_context

PACK_ROOT = ROOT / "demo/competition_v1"


def scenario_note(scenario, batch):
    key = scenario["key"]
    intro = f"# {scenario['title']}\n\n全部为模拟业务材料。当前待办：{scenario['nextAction']}\n\n## 第一条对话指令\n{scenario['prompt']}\n\n"
    notes = {
        "de_a": """## 从询盘到报价
1. 在右侧对话分析需求；展开“引用知识与核价条件”，选择规格、核价、FOB 三篇 Wiki。
2. 选择“工厂 A｜宁波远行箱包（模拟）”，汇率 7.2、毛利率 20、数量 3000。
3. 发送：请核算3000件背包报价。预期 USD 8.69/件，商品小计 USD 26,070。
4. 每轮成果自动保存，打开“对话成果汇总”查看；业务资料与审批中可查看五类成果及下载草稿。
5. 规格、包装、付款等具体字段可用 sources/spec-DE-v1.txt 和 edits/spec-DE-v1.json 核对维护。
6. 后续彩盒、订单与确认材料在公司资产库，只有进入相应阶段才登记为当前 Case 证据。
## 一条 Case 继续跑完整主链路
可使用手册中的 quote → change → order → approve → release 五条辅助命令；每条都调用真实业务接口，批准和放行须单独执行。
""",
        "de_b": """## 包装变更续办
已有模拟历史规格/成本/报价 V1，单价 USD 8.69；没有预先登记新的业务批准。
1. 打开“业务资料与审批”，选择 customer-packaging-change.eml 作为变更来源。
2. 输入：包装从普通纸盒改为定制彩盒，成本和交期需更新。点“分析变更影响”。
3. 点“生成联动修订草稿”。检查旧版仍保留，候选成本/报价因待确认暂为空。
4. 按工厂 A 彩盒新版原件维护候选规格、RFQ、成本、报价。手工保存必须产生新版本。
5. 每个受影响节点关联对应新成果；尚未下单的样品/PO/生产节点说明依据，后续使用新规格。
6. 处理完节点后激活，再用工厂 A 彩盒新版核价。预期 USD 9.21/件、USD 27,630，总额增加 USD 1,560。
为了节省比赛时间，可先在界面展示影响和候选版，再运行手册中的 change 辅助命令完成繁琐逐节点维护。
""",
        "de_c": """## PO、样品、订单与生产门禁
已有模拟历史规格/报价 V1、V2；V2 包装为彩盒、单价 USD 9.21。PO/PI/生产指令/T&A/QC 都是待审核草稿。
1. 不运行新 Agent 任务，先在“业务资料与审批”点击“检查生产资料门禁”，应显示六项缺口。
2. 审批范围“客户规格确认”：选择 customer-final-approval.eml，记录批准。
3. 审批范围“内部报价批准”：核对最新报价 V2 的 USD 9.21/件、付款及 FOB 条款，再记录批准。
4. 样品批准：选择 customer-final-approval.eml，记录样品批准，绑定最新规格。
5. 订单：选择 PO-DE-001-V2.pdf；买方 customer-final-approval.eml，卖方 seller-order-acceptance.eml，记录双方确认。
6. 付款：选择 payment-advice.txt；填写“模拟核验 DEMO-PAY-DE-001，30%定金 USD8289，与PO总额USD27630一致”，记录核验。
7. 审批范围“供应商生产确认”：选择 supplier-production-confirmation.eml，记录当前业务版本批准。
8. 再检查门禁，应通过；最后点击对应资料包的“人工放行”。这是资料包放行，不是实际开工。
若运行新任务生成新业务版本或新规格，须重新确认受影响的版本，不要沿用旧批准。
""",
        "mx": """## MOQ 与西语试单
1. 初始客户数量 300，供应商 MOQ 500。分析后尝试按 300 核价应阻断。
2. 从公司资产库查看 mx-quantity-confirmation.eml，客户同意改为 600，仅确认数量。
3. 选择工厂 M，汇率7.2、毛利率25、数量600。发送：客户已确认数量600件帆布袋，请核算报价。
4. 预期 USD3.43/件，商品小计USD2058；生产预计18天，不自动承诺30天到货。
5. 西语草稿可编辑保存；没有样品批准/订单/付款保障时生产仍应阻断。
""",
        "uk": """## 信息不足与澄清恢复
1. 发送第一条指令，任务应显示 needs_input，询问产品类型和已知需求。
2. 刷新页面，待回答任务仍存在。
3. 对照 uk-clarification-reply.eml，在输入框填：客户补充800件电脑包，15.6英寸、深灰色、定制LOGO，伦敦；材料和具体尺寸待确认，仅整理需求，不报价。
4. 提交后恢复同一 Run，生成需求和缺项，无有效报价。
5. 没有供应商成本时请求核价应再次要求补充，而不是虚构单价。
""",
    }
    return intro + notes[key] + f"\n资料包目录：demo/competition_v1\n批次：{batch}\n完整手册：demo/competition_v1/演示操作手册.md\n"


def asset(db, user, file):
    identifier = f"demoasset_competition_v1_{file['key']}"
    row_id = f"{identifier}:v1"
    row = db.get(Item, row_id)
    if row:
        return item_view(row)
    path = PACK_ROOT / file["file"]
    media = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    blob = store_blob(db, path.read_bytes(), path.name, media)
    value = {"id": identifier, "name": path.name, "title": path.name, "version": 1, "space": "company",
             "ownerId": user.id, "folder": "比赛演示/后续阶段" if file["future"] else "比赛演示/询盘与报价",
             "mediaType": media, "size": blob.byte_size, "blobId": blob.id, "createdAt": now(),
             "skuScope": [], "locale": "zh-CN", "source": "比赛模拟原件，非真实交易", "simulation": True}
    create_item(db, "asset", value, item_id=row_id, parent_id=identifier)
    return value


def seed_baseline(db, case, scenario, offers, refs, pack):
    """Import explicitly labeled historical fixtures, without executing approvals."""
    for version in range(1, scenario["baseline"] + 1):
        selected = offers["a2" if version == 2 else "a1"]
        spec = pack["spec2" if version == 2 else "spec1"]
        cost = {"base": selected["baseCny"], "packaging": selected["packagingCny"], "local": selected["localCny"], "exchangeRate": "7.2", "margin": "20", "quantity": 3000}
        job_id, run_id = f"demojob_{case.id}_{version}", f"demorun_{case.id}_{version}"
        summary = f"导入模拟历史报价 V{version}，不是本次 Agent 执行记录；未自动登记商业批准。"
        job = Job(id=job_id, case_id=case.id, kind="prepare_quote", goal=summary, graph_version="demo-history-v1", status="completed", payload=encode({"simulation": True, "importedBaseline": True, "sourceRefs": refs}))
        db.add(job); db.flush()
        run = Run(id=run_id, job_id=job_id, case_id=case.id, base_revision=version-1, action="import_demo_history", instruction=summary, status="succeeded", phase="committing", output_revision=version, payload=encode({"simulation": True, "completedPhases": []}))
        db.add(run); db.flush()
        facts = {"product": "backpack", "quantity": 3000, "destination": "Hamburg", "specification": spec["material"] + "; " + spec["dimensions"], "customization": spec["logo"], "requested_arrival": "45天到港为期望，需另核实船期", "missing_fields": ["shippingSchedule"]}
        state = {"kind": "prepare_quote", "extracted": facts, "quote": price_quote(cost), "costInputs": cost, "supplierOffers": list(offers.values()), "selectedSupplierOfferId": selected["id"], "input_refs": [selected["evidenceSourceId"]], "summary": summary, "risks": []}
        rev = build_revision(case, run, state)
        rev.update(sourceRefs=refs, simulation=True, importedBaseline=True)
        create_item(db, "revision", rev, case_id=case.id, parent_id=case.id, version=version, item_id=f"demorev_{case.id}_{version}")
        for locale, text in rev["replies"].items():
            create_item(db, "draft", {"inquiryId": case.id, "revision": version, "locale": locale, "draftVersion": 1, "text": text, "reviewStatus": "needs_review", "updatedAt": now()}, case_id=case.id, parent_id=f"{case.id}:{version}:{locale}", item_id=f"demodraft_{case.id}_{version}_{locale}")
        for a in draft_node(state)["artifacts"]:
            if a["kind"] == "spec": a["content"] = spec
            if a["kind"] == "quotation":
                a["content"].update(incoterm="FOB", namedPlace="Ningbo", incotermsVersion="2020", paymentTerms="30% deposit, 70% before shipment", validUntil="2026-11-14", productionTime=f"{selected['leadDays']} days after final approval and payment conditions", sampleTime="7 days" if version==2 else "5 days")
            create_item(db, "artifact", {**a, "caseId": case.id, "version": version, "status": "draft", "simulation": True, "importedBaseline": True, "jobId": job_id, "runId": run_id, "createdAt": now()}, case_id=case.id, parent_id=a["kind"], version=version, item_id=f"artifact_{case.id}_{a['kind']}_v{version}")
        case.current_revision = version
        create_item(db, "message", {"inquiryId": case.id, "role": "assistant", "text": summary, "runId": run_id, "createdAt": now()}, case_id=case.id, item_id=f"demomsg_{case.id}_{version}")


def seed(batch="competition", email=None):
    if os.getenv("APP_ENV", "demo") != "demo":
        raise SystemExit("演示包只允许在 APP_ENV=demo 环境导入")
    if not re.fullmatch(r"[a-z0-9_-]{1,32}", batch):
        raise SystemExit("batch 仅允许 1-32 位小写字母、数字、横线和下划线")
    pack = json.loads((PACK_ROOT / "pack.json").read_text(encoding="utf-8"))
    for file in pack["files"]:
        if not (PACK_ROOT / file["file"]).exists():
            raise SystemExit(f"缺少材料：{file['file']}")
    Base.metadata.create_all(engine)
    report = {"batch": batch, "simulation": True, "cases": {}, "sources": {}, "assets": {}}
    with SessionLocal() as db:
        bootstrap(db)
        user = db.scalar(select(User).where(User.email == (email or os.getenv("DEMO_EMAIL", "demo@navowork.local")).lower()))
        if not user:
            raise SystemExit("目标账户不存在；请先创建或登录演示账户")
        refs = []
        for wiki in pack["wiki"]:
            source_id = f"demo_knowledge_{wiki['key']}"
            content = (PACK_ROOT / wiki["file"]).read_text(encoding="utf-8")
            row = db.get(Item, f"{source_id}:v1")
            if not row:
                row = create_item(db, "resource", {"id": source_id, "sourceId": source_id, "kind": "knowledge", "title": wiki["title"], "folder": wiki["folder"], "content": content, "status": "published", "version": 1, "editVersion": 1, "ownerId": user.id, "updatedAt": now(), "simulation": True}, item_id=f"{source_id}:v1", parent_id=source_id, status="published")
            actual = item_view(row)
            refs.append({"sourceVersionId": row.id, "sourceId": source_id, "version": 1, "title": actual["title"], "contentHash": hashlib.sha256(actual["content"].encode()).hexdigest(), "locator": {}, "supports": ["simulation_reference"]})
            report["sources"][wiki["key"]] = row.id
        assets = {f["key"]: asset(db, user, f) for f in pack["files"]}
        report["assets"] = {k: v["id"]+":v1" for k,v in assets.items()}
        db.flush()
        for index, scenario in enumerate(pack["scenarios"]):
            key = scenario["key"]
            case_id = f"inq_{batch}_{key}"
            existing = db.get(Case, case_id)
            if existing:
                if not db.get(CaseAccess, (case_id, user.id)):
                    raise SystemExit("同名批次不属于当前账户，请使用新的 --batch")
                existing_data = decode(existing.payload)
                if existing_data.get("simulation") and not existing_data.get("customerContext"):
                    existing_data["customerContext"] = customer_context(key)
                    existing.payload = encode(existing_data)
                    existing.metadata_version += 1
                report["cases"][key] = {"id": case_id, "title": existing_data["title"], "preserved": True}
                continue
            case = Case(id=case_id, workspace_id=WORKSPACE_ID, owner_id=user.id, status="todo", payload=encode({"title": scenario["title"] + (f" / {batch}" if batch != "competition" else ""), "customer": scenario["customer"], "originalText": scenario["originalText"], "requestedLocales": ["en-US", "es-MX"], "destination": scenario["destination"], "nextAction": scenario["nextAction"], "simulation": True, "demoBatch": batch, "demoScenario": key}))
            db.add(case); db.flush()
            case.payload = encode({**decode(case.payload), "customerContext": customer_context(key)})
            db.add(CaseAccess(case_id=case_id, user_id=user.id))
            create_item(db, "message", {"inquiryId": case_id, "role": "user", "text": scenario["originalText"], "createdAt": now()}, case_id=case_id, item_id=f"demoinquiry_{case_id}")
            evmap = {}
            for file in pack["files"]:
                if key not in file["cases"]: continue
                a = assets[file["key"]]
                from app.sop_api import _extract_file
                path = PACK_ROOT / file["file"]
                content = _extract_file(path.read_bytes(), path.name)
                ev_id = f"demoevidence_{case_id}_{file['key']}"
                evmap[file["key"]] = ev_id
                create_item(db, "evidence", {"id": ev_id, "caseId": case_id, "title": path.name + "【模拟】", "sourceRole": file["role"], "blobId": a["blobId"], "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "text": content, "parseStatus": "pending", "simulation": True, "status": "observed", "createdAt": now()}, case_id=case_id, item_id=ev_id, status="observed")
            offers = {}
            for offer in pack["offers"]:
                if key not in offer["cases"]: continue
                offer_id = f"demooffer_{case_id}_{offer['key']}"
                value = {k:v for k,v in offer.items() if k not in ("key", "sheet", "cases")}
                value.update(id=offer_id, caseId=case_id, evidenceSourceId=evmap["offer_"+offer["key"]], currency="CNY", includesPackaging=False, status="observed", simulation=True, notes=f"人工预录入模拟原件 {offer['sheet']}；本地费用为内部假设，核价仍需运行。", createdAt=now())
                create_item(db, "supplier_offer", value, case_id=case_id, item_id=offer_id, status="observed")
                offers[offer["key"]] = value
            db.flush()
            seed_baseline(db, case, scenario, offers, refs[1:4], pack)
            if key == "de_c":
                extras = production_templates(case_id, pack)
                for kind, content in extras.items():
                    create_item(db, "artifact", {"kind": kind, "title": {"pi":"PI 草稿", "production":"生产指令草稿", "ta":"T&A 相对节点计划", "qc":"QC 检查清单"}[kind], "content": content, "version": 1, "status": "draft", "simulation": True, "createdAt": now()}, case_id=case_id, parent_id=kind, item_id=f"artifact_{case_id}_{kind}_v1")
            case.status = "todo"
            note = {"id": "note:demo-guide", "title": "00 演示操作卡（先读）", "folder": "notes", "text": scenario_note(scenario, batch)}
            file_entries = []
            relevant_keys = set(evmap) | ({"drawing", "workbook"} if key.startswith("de_") else {"workbook"} if key=="mx" else set())
            for k in sorted(relevant_keys):
                a = assets[k]
                file_entries.append({"id": f"asset:{a['id']}:v1", "assetId": a["id"], "version": 1, "name": a["name"], "title": a["title"], "mediaType": a["mediaType"], "size": a["size"], "folder": "materials"})
            canvas = {"schema": 1, "positions": {"note:demo-guide": {"x": 0, "y": 68}}, "tabs": [note["id"]], "active": note["id"], "folders": [], "notes": [note], "files": file_entries, "drafts": {}, "initialRevision": case.current_revision, "results": []}
            create_item(db, "canvas", canvas, case_id=case_id, parent_id=user.id, item_id=f"canvas:{case_id}:{user.id}")
            report["cases"][key] = {"id": case_id, "title": scenario["title"], "evidence": evmap, "offers": {k:v["id"] for k,v in offers.items()}, "revision": case.current_revision}
        db.commit()
    out = ROOT / "backend/data" / f"demo-{batch}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for k,v in report["cases"].items():
        print(f"{k}: http://127.0.0.1:5173/inquiries/{v['id']}" + (" (existing work preserved)" if v.get("preserved") else ""))
    print(f"Wiki: {len(refs)}; company assets: {len(assets)}; cases: {len(report['cases'])}. No approvals or releases recorded.")
    return report


def production_templates(case_id, pack):
    return {
        "pi": {"buyer":"Nordlicht Outdoor GmbH (fictional)", "seller":"NavoWork Demo Trading (fictional)", "product":"BP-DE-3000 backpack / CB-02", "quantity":3000, "unitPrice":"9.21", "total":"27630.00", "currency":"USD", "incoterm":"FOB", "namedPlace":"Ningbo", "incotermsVersion":"2020", "paymentTerms":"30% deposit USD8289; 70% balance USD19341 before shipment", "po":"PO-DE-001-V2", "bilateralConfirmation":None, "status":"draft", "simulation":True},
        "production": {"product":"BP-DE-3000", "quantity":3000, "specification":pack["spec2"], "sample":"SMP-DE-CB02", "packagingArtwork":"CB-02", "productionLeadDays":31, "startsAfter":"All release prerequisites met", "released":False, "status":"draft", "simulation":True},
        "ta": {"anchor":"D0 = human release after all approvals and payment assurance; no fixed arrival commitment", "tasks":[{"day":"D0-D3", "task":"material and artwork reconfirmation", "owner":"Factory A"}, {"day":"D4-D9", "task":"cutting and embroidery", "owner":"Factory A"}, {"day":"D10-D22", "task":"sewing and assembly", "owner":"Factory A"}, {"day":"D23-D27", "task":"finishing and internal QC", "owner":"Factory A"}, {"day":"D28-D31", "task":"packing and agreed pre-shipment inspection", "owner":"Factory / inspector"}], "shipping":"booking and sea transit pending", "status":"draft", "simulation":True},
        "qc": {"standard":pack["spec2"]["inspectionStandard"], "checks":["dimensions and tolerance", "material / color", "logo and placement", "stitches / zippers / straps", "laptop sleeve and pockets", "CB-02 artwork and box fit", "20 pcs/carton and marks"], "result":None, "inspectionEvidence":None, "status":"draft", "simulation":True},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", default="competition")
    parser.add_argument("--email")
    args = parser.parse_args()
    seed(args.batch, args.email)
