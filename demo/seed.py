"""Seed the Workbench v2 demo: sources, knowledge and assets only.

This script deliberately does NOT create revisions, specs, quotations,
approvals, samples, orders or production packs. The user advances each node
through the Agent. Run from the repository root:

    python demo/seed.py
"""
from __future__ import annotations

import argparse
import hashlib
import mimetypes
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dev import local_env  # noqa: E402

os.environ.update(local_env())
os.chdir(ROOT / "backend")
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core import WORKSPACE_ID, bootstrap, create_item, decode, encode, item_view, store_blob  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Case, CaseAccess, Item, User, now  # noqa: E402
from app.sop_api import _extract_file  # noqa: E402

PACK = ROOT / "demo/workbench_v2"


def ensure_resource(db, user, slug: str, title: str, folder: str, path: Path):
    source_id = f"kb_workbench_{slug}"
    content = path.read_text(encoding="utf-8")
    row = db.get(Item, f"{source_id}:v1")
    value = {
        "id": source_id,
        "sourceId": source_id,
        "kind": "knowledge",
        "title": title,
        "folder": folder,
        "content": content,
        "status": "published",
        "version": 1,
        "editVersion": 1,
        "ownerId": user.id,
        "updatedAt": now(),
    }
    if row:
        row.payload = encode(value)
        row.status = "published"
    else:
        create_item(db, "resource", value, item_id=f"{source_id}:v1", parent_id=source_id, status="published")
    return f"{source_id}:v1"


def ensure_asset(db, user, key: str, path: Path, folder: str):
    asset_id = f"asset_workbench_{key}"
    row = db.get(Item, f"{asset_id}:v1")
    if row:
        return item_view(row)
    media = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    blob = store_blob(db, path.read_bytes(), path.name, media)
    value = {
        "id": asset_id,
        "name": path.name,
        "title": path.stem.replace("-", " ").title(),
        "version": 1,
        "space": "company",
        "ownerId": user.id,
        "folder": folder,
        "mediaType": media,
        "size": blob.byte_size,
        "blobId": blob.id,
        "createdAt": now(),
        "skuScope": [],
        "locale": "zh-CN",
        "source": "Nordlicht 项目资料",
    }
    create_item(db, "asset", value, item_id=f"{asset_id}:v1", parent_id=asset_id)
    return value


def evidence(db, case: Case, key: str, filename: str, role: str, title: str | None = None):
    path = PACK / "sources" / filename
    data = path.read_bytes()
    media = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    blob = store_blob(db, data, path.name, media, case.id)
    item_id = f"ev_workbench_{case.id}_{key}"
    text = _extract_file(data, path.name)
    value = {
        "id": item_id,
        "caseId": case.id,
        "title": title or path.name,
        "sourceRole": role,
        "blobId": blob.id,
        "sha256": hashlib.sha256(data).hexdigest(),
        "text": text,
        "parseStatus": "pending",
        "status": "observed",
        "createdAt": now(),
    }
    create_item(db, "evidence", value, case_id=case.id, item_id=item_id, status="observed")
    return item_id


CUSTOMERS = {
    "de": {
        "channel": "website",
        "sourceRef": "官网询盘表单 #NL-2026-0412",
        "email": "michael.weber@nordlicht-outdoor.de",
        "website": "https://nordlicht-outdoor.de",
        "linkedin": "https://www.linkedin.com/company/nordlicht-outdoor",
        "company": "Nordlicht Outdoor GmbH",
        "country": "Germany",
        "business": "户外用品零售与自有品牌开发；门店与线上渠道，背包、旅行配件为主。",
        "summary": "客户名称、域名与联系邮箱一致；采购决策人尚未确认，付款信誉与公司注册信息需在订单前核验。",
        "checks": [
            {"label": "公司名称与域名", "status": "matched", "detail": "邮件域名与官网一致"},
            {"label": "采购决策人", "status": "review", "detail": "Michael Weber 的采购权限待确认"},
            {"label": "付款信誉", "status": "pending", "detail": "首次合作，订单前核验"},
        ],
    },
    "mx": {
        "channel": "amazon",
        "sourceRef": "Amazon 商家询盘 MX-2026-118",
        "email": "sofia@casa-verde.mx",
        "website": "",
        "linkedin": "",
        "company": "Casa Verde",
        "country": "Mexico",
        "business": "生活方式礼品与帆布袋零售；线上店铺为主，希望先做小批量试单。",
        "summary": "客户为墨西哥城礼品零售商；首单数量低于常规 MOQ，需先确认数量与交期。",
        "checks": [
            {"label": "公司名称与邮箱", "status": "matched", "detail": "邮件签名与询盘信息一致"},
            {"label": "采购数量", "status": "review", "detail": "300 件低于工厂 MOQ 500"},
            {"label": "付款信誉", "status": "pending", "detail": "首次合作，订单前核验"},
        ],
    },
    "uk": {
        "channel": "email",
        "sourceRef": "邮件询盘 UK-2026-077",
        "email": "emma@harbor-promotions.co.uk",
        "website": "",
        "linkedin": "",
        "company": "Harbor Promotions",
        "country": "United Kingdom",
        "business": "促销礼品代理商，终端客户活动采购。",
        "summary": "询盘信息不足：只有产品大类、目的地和可能的 Logo 需求，数量和规格未提供。",
        "checks": [
            {"label": "公司名称与邮箱", "status": "matched", "detail": "公司域名邮箱"},
            {"label": "产品与数量", "status": "pending", "detail": "未提供具体产品、尺寸和数量"},
            {"label": "交期", "status": "pending", "detail": "仅写 as soon as possible"},
        ],
    },
}

CASES = {
    "de": {
        "id": "inq_demo_de",
        "title": "Nordlicht Outdoor · 定制通勤背包",
        "customer": "Michael Weber / Nordlicht Outdoor",
        "original": "de-inquiry.eml",
        "destination": "Hamburg, Germany",
        "nextAction": "阅读询盘，整理客户背景与需求；再让 Agent 生成 Tech Pack 与 BOM",
        "files": [
            ("inquiry", "de-inquiry.eml", "customer_request", "客户询盘"),
            ("quote_a", "supplier-a-quote.txt", "supplier_quote", "工厂 A 报价"),
            ("quote_b", "supplier-b-quote.txt", "supplier_quote", "工厂 B 报价"),
            ("change", "customer-change.eml", "customer_change", "客户包装变更"),
            ("po", "po-de-001.txt", "customer_po", "客户 PO"),
            ("sample_feedback", "sample-feedback.eml", "sample_inspection", "样品反馈"),
            ("spec_approval", "customer-spec-approval.eml", "customer_approval", "客户规格批准"),
            ("sample_approval", "customer-sample-approval.eml", "customer_approval", "客户样品批准"),
            ("internal_quote", "internal-quotation-approval.eml", "internal_note", "内部报价批准"),
            ("seller_accept", "seller-order-acceptance.eml", "internal_note", "卖方订单确认"),
            ("supplier_confirm", "supplier-production-confirmation.eml", "supplier_confirmation", "供应商生产确认"),
            ("payment", "payment-advice.txt", "payment_receipt", "定金到账凭据"),
        ],
    },
    "mx": {
        "id": "inq_demo_mx",
        "title": "Casa Verde · 帆布袋试单",
        "customer": "Sofia Martinez / Casa Verde",
        "original": "mx-inquiry.eml",
        "destination": "Mexico City, Mexico",
        "nextAction": "先确认 300 件与 MOQ 500 的差异，再整理规格",
        "files": [
            ("inquiry", "mx-inquiry.eml", "customer_request", "客户询盘"),
            ("quote", "mx-supplier-quote.txt", "supplier_quote", "工厂 M 报价"),
        ],
    },
    "uk": {
        "id": "inq_demo_uk",
        "title": "Harbor Promotions · 信息不足询盘",
        "customer": "Emma Brown / Harbor Promotions",
        "original": "uk-inquiry.eml",
        "destination": "London, United Kingdom",
        "nextAction": "先澄清产品、数量、规格和交期；不要报价",
        "files": [
            ("inquiry", "uk-inquiry.eml", "customer_request", "客户询盘"),
        ],
    },
}

WIKI = [
    ("customer", "客户与询盘评估", "业务流程", "01-customer-inquiry.md"),
    ("techpack", "箱包 Tech Pack 与 BOM", "产品与规格", "02-bag-techpack.md"),
    ("costing", "成本核算与报价", "报价与条款", "03-costing-quotation.md"),
    ("trade", "贸易术语与付款方式", "报价与条款", "04-trade-terms.md"),
    ("sample", "打样与样品确认", "样品与订单", "05-sample.md"),
    ("order", "订单、PI 与付款保障", "样品与订单", "06-order-pi.md"),
    ("production", "生产资料、T&A 与验货", "生产与验货", "07-production-qc.md"),
    ("materials", "箱包材料与辅料参考", "产品与规格", "08-bag-materials.md"),
]


def seed(email: str | None = None):
    if os.getenv("APP_ENV", "demo") != "demo":
        raise SystemExit("演示包只允许在 APP_ENV=demo 环境导入")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        bootstrap(db)
        user = db.scalar(select(User).where(User.email == (email or os.getenv("DEMO_EMAIL", "demo@navowork.local")).lower()))
        if not user:
            raise SystemExit("目标账户不存在；请先创建演示账户")
        for slug, title, folder, filename in WIKI:
            ensure_resource(db, user, slug, title, folder, PACK / "wiki" / filename)
        for key, filename, folder in (
            ("product", "product-reference.svg", "产品图片"),
            ("po", "po-de-001.txt", "订单与单证"),
            ("payment", "payment-advice.txt", "订单与单证"),
        ):
            ensure_asset(db, user, key, PACK / "sources" / filename, folder)
        db.flush()
        for key, scenario in CASES.items():
            path = PACK / "sources" / scenario["original"]
            original = path.read_text(encoding="utf-8")
            existing = db.get(Case, scenario["id"])
            if existing:
                print(f"{key}: 已存在，保留 {scenario['id']}")
                continue
            payload = {
                "title": scenario["title"],
                "customer": scenario["customer"],
                "originalText": original,
                "requestedLocales": ["en-US"],
                "destination": scenario["destination"],
                "nextAction": scenario["nextAction"],
                "customerContext": CUSTOMERS[key],
            }
            case = Case(id=scenario["id"], workspace_id=WORKSPACE_ID, owner_id=user.id, payload=encode(payload), status="todo")
            db.add(case)
            db.flush()
            db.add(CaseAccess(case_id=case.id, user_id=user.id))
            for file_key, filename, role, title in scenario["files"]:
                evidence(db, case, file_key, filename, role, title)
            db.flush()
        db.commit()
    print("Workbench v2 seed complete. No revisions, artifacts or approvals were created.")
    for key, scenario in CASES.items():
        print(f"{key}: http://127.0.0.1:5173/inquiries/{scenario['id']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email")
    args = parser.parse_args()
    seed(args.email)
