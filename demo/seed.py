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
from app.models import Case, CaseAccess, Item, User, now
from customer_profiles import customer_context

PACK_ROOT = ROOT / "demo/competition_v1"


DEFAULT_BATCH = "intake"
RESOURCE_VERSION = 2
INITIAL_FILES = {"de_a": "inquiry", "de_b": "inquiry", "de_c": "inquiry", "mx": "mx_inquiry", "uk": "uk_inquiry"}


def asset(db, user, file, *, root=PACK_ROOT, namespace="competition_v1"):
    """Keep source bytes immutable; a changed source becomes a new asset version."""
    from app.sop_api import _extract_file
    identifier = f"demoasset_{namespace}_{file['key']}"
    path = root / file["file"]
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    rows = list(db.scalars(select(Item).where(Item.kind == "asset", Item.parent_id == identifier).order_by(Item.version.desc())))
    if rows and item_view(rows[0]).get("sha256") == digest:
        return item_view(rows[0])
    version = (rows[0].version + 1) if rows else 1
    media = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    blob = store_blob(db, data, path.name, media)
    stage = file.get("stage") or ("requirements" if "inquiry" in file["key"] else "supplier-costing" if file["role"] == "supplier_quote" else "order" if file.get("future") else "specification")
    value = {"id": identifier, "name": path.name, "title": file.get("title", path.name), "version": version,
             "space": "company", "ownerId": user.id, "folder": file.get("folder") or {"requirements": "询盘资料", "specification": "产品与规格", "supplier-costing": "供应商报价", "order": "样品与订单"}.get(stage, "业务资料"),
             "mediaType": media, "size": blob.byte_size, "blobId": blob.id, "createdAt": now(),
             "skuScope": [], "locale": "zh-CN", "source": file.get("source", "业务资料"), "simulation": True,
             "sourceRole": file["role"], "stage": stage, "textContent": _extract_file(data, path.name),
             "sha256": digest, "sourceGroup": namespace, "requiresExplicitSelection": True}
    create_item(db, "asset", value, item_id=f"{identifier}:v{version}", parent_id=identifier, version=version)
    return value


def core_assets(db, user):
    root = ROOT / "test/core15"
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stage_map = {1: ("requirements", "客户与询盘", "internal_note"), 2: ("requirements", "客户与询盘", "customer_request"),
        3: ("requirements", "客户与询盘", "internal_note"), 4: ("specification", "需求与规格", "customer_request"),
        5: ("specification", "需求与规格", "customer_request"), 6: ("check-quality", "包装与验货", "customer_request"),
        7: ("specification", "需求与规格", "customer_approval"), 8: ("supplier-costing", "询价与核价", "supplier_quote"),
        9: ("supplier-costing", "询价与核价", "internal_note"), 10: ("quotation", "询价与核价", "internal_note"),
        11: ("sample-feedback", "打样与确认", "internal_note"), 12: ("sample-feedback", "打样与确认", "sample_inspection"),
        13: ("sample-feedback", "打样与确认", "customer_approval"), 14: ("po-check", "订单与合同", "customer_po"),
        15: ("production", "订单与合同", "customer_request")}
    result = {}
    for category in manifest["categories"]:
        stage, folder, role = stage_map[category["id"]]
        for filename in category["files"]:
            if not (root / filename).exists():
                continue
            if filename.startswith(("14b_", "14c_")):
                role = "internal_note"
            file = {"key": Path(filename).stem, "file": filename, "role": role, "stage": stage,
                    "folder": "核心业务资料/" + folder, "title": category["name_zh"] + " · " + Path(filename).stem,
                    "source": "BAG-2026-DE-001 · V3 资料档案"}
            result[file["key"]] = asset(db, user, file, root=root, namespace="core15")
    roles = {"E01": "customer_approval", "E02": "supplier_confirmation", "E03": "sample_inspection", "E04": "customer_approval", "E05": "internal_note", "E06": "internal_note"}
    for source in manifest["evidence"]:
        file = {"key": Path(source["path"]).stem, "file": source["path"], "role": roles.get(source.get("alias"), "customer_change" if "change" in source["path"] else "customer_request"),
                "stage": "sample-feedback" if "sample" in source["path"] else "specification", "folder": "核心业务资料/往来原件", "source": "BAG-2026-DE-001 · 往来原件"}
        result[file["key"]] = asset(db, user, file, root=root, namespace="core15")
    return result


def seed(batch=DEFAULT_BATCH, email=None):
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
            raise SystemExit("目标账户不存在；请先创建或登录账户")
        for wiki in pack["wiki"]:
            source_id = f"demo_knowledge_{wiki['key']}"
            content = (PACK_ROOT / wiki["file"]).read_text(encoding="utf-8")
            rows = list(db.scalars(select(Item).where(Item.kind == "resource", Item.parent_id == source_id).order_by(Item.version.desc())))
            latest = item_view(rows[0]) if rows else None
            if latest and latest.get("content") == content and latest.get("title") == wiki["title"]:
                row = rows[0]
            else:
                version = rows[0].version + 1 if rows else 1
                row = create_item(db, "resource", {"id": source_id, "sourceId": source_id, "kind": "knowledge", "title": wiki["title"], "folder": wiki["folder"], "content": content,
                    "status": "published", "version": version, "editVersion": 1, "ownerId": user.id, "updatedAt": now()}, item_id=f"{source_id}:v{version}", parent_id=source_id, status="published", version=version)
            report["sources"][wiki["key"]] = row.id
        assets = {f["key"]: asset(db, user, f) for f in pack["files"]}
        imported_core = core_assets(db, user)
        report["assets"] = {k: f"{v['id']}:v{v['version']}" for k, v in assets.items()}
        report["core15Assets"] = {k: f"{v['id']}:v{v['version']}" for k, v in imported_core.items()}
        db.flush()
        for scenario in reversed(pack["scenarios"]):
            key = scenario["key"]
            case_id = f"inq_{batch}_{key}"
            existing = db.get(Case, case_id)
            if existing:
                if not db.get(CaseAccess, (case_id, user.id)):
                    raise SystemExit("同名批次不属于当前账户，请使用新的 --batch")
                report["cases"][key] = {"id": case_id, "title": decode(existing.payload)["title"], "preserved": True}
                continue
            payload = {"title": scenario["title"], "customer": scenario["customer"], "originalText": scenario["originalText"],
                "requestedLocales": ["en-US", "es-MX"], "destination": scenario["destination"], "nextAction": scenario["nextAction"],
                "simulation": True, "demoBatch": batch, "demoScenario": key, "customerContext": customer_context(key)}
            case = Case(id=case_id, workspace_id=WORKSPACE_ID, owner_id=user.id, status="todo", payload=encode(payload))
            db.add(case); db.flush()
            db.add(CaseAccess(case_id=case_id, user_id=user.id))
            create_item(db, "message", {"inquiryId": case_id, "role": "user", "text": scenario["originalText"], "createdAt": now()}, case_id=case_id, item_id=f"demoinquiry_{case_id}")
            file = next(f for f in pack["files"] if f["key"] == INITIAL_FILES[key])
            a = assets[file["key"]]
            ev_id = f"demoevidence_{case_id}_{file['key']}"
            create_item(db, "evidence", {"id": ev_id, "caseId": case_id, "title": a["name"], "sourceRole": "customer_request", "blobId": a["blobId"],
                "sha256": a["sha256"], "text": a["textContent"], "parseStatus": "pending", "simulation": True, "status": "observed", "createdAt": now()}, case_id=case_id, item_id=ev_id, status="observed")
            file_entry = {"id": f"asset:{a['id']}:v{a['version']}", "assetId": a["id"], "version": a["version"], "name": a["name"], "title": a["title"], "mediaType": a["mediaType"], "size": a["size"], "folder": "materials"}
            canvas = {"schema": 1, "positions": {}, "tabs": [], "active": "", "folders": [], "notes": [], "files": [file_entry], "drafts": {}, "initialRevision": 0, "results": []}
            create_item(db, "canvas", canvas, case_id=case_id, parent_id=user.id, item_id=f"canvas:{case_id}:{user.id}")
            report["cases"][key] = {"id": case_id, "title": scenario["title"], "evidence": {file["key"]: ev_id}, "offers": {}, "revision": 0}
        db.commit()
    out = ROOT / "backend/data" / f"demo-{batch}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for key, value in report["cases"].items():
        print(f"{key}: http://127.0.0.1:5173/inquiries/{value['id']}" + (" (existing work preserved)" if value.get("preserved") else ""))
    print(f"Wiki: {len(report['sources'])}; company assets: {len(assets) + len(imported_core)}; cases: {len(report['cases'])}. New cases contain original inquiries only.")
    return report


def production_templates(case_id, pack):
    return {
        "pi": {"buyer":"Nordlicht Outdoor GmbH", "seller":"NavoWork Trading", "product":"BP-DE-3000 backpack / CB-02", "quantity":3000, "unitPrice":"9.21", "total":"27630.00", "currency":"USD", "incoterm":"FOB", "namedPlace":"Ningbo", "incotermsVersion":"2020", "paymentTerms":"30% deposit USD8289; 70% balance USD19341 before shipment", "po":"PO-DE-001-V2", "bilateralConfirmation":None, "status":"draft", "simulation":True},
        "production": {"product":"BP-DE-3000", "quantity":3000, "specification":pack["spec2"], "sample":"SMP-DE-CB02", "packagingArtwork":"CB-02", "productionLeadDays":31, "startsAfter":"All release prerequisites met", "released":False, "status":"draft", "simulation":True},
        "ta": {"anchor":"D0 = human release after all approvals and payment assurance; no fixed arrival commitment", "tasks":[{"day":"D0-D3", "task":"material and artwork reconfirmation", "owner":"Factory A"}, {"day":"D4-D9", "task":"cutting and embroidery", "owner":"Factory A"}, {"day":"D10-D22", "task":"sewing and assembly", "owner":"Factory A"}, {"day":"D23-D27", "task":"finishing and internal QC", "owner":"Factory A"}, {"day":"D28-D31", "task":"packing and agreed pre-shipment inspection", "owner":"Factory / inspector"}], "shipping":"booking and sea transit pending", "status":"draft", "simulation":True},
        "qc": {"standard":pack["spec2"]["inspectionStandard"], "checks":["dimensions and tolerance", "material / color", "logo and placement", "stitches / zippers / straps", "laptop sleeve and pockets", "CB-02 artwork and box fit", "20 pcs/carton and marks"], "result":None, "inspectionEvidence":None, "status":"draft", "simulation":True},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", default=DEFAULT_BATCH)
    parser.add_argument("--email")
    args = parser.parse_args()
    seed(args.batch, args.email)
