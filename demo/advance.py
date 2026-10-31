"""Stage-by-stage demo helper. All business writes go through the real HTTP API.

Use --step approve / release explicitly to record simulated human decisions.
Only the seeded fictional German cases are accepted. No external messages sent.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlparse

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dev import local_env

PACK_ROOT = ROOT / "demo/competition_v1"
PACK = json.loads((PACK_ROOT / "pack.json").read_text(encoding="utf-8"))
PREFIX = "/api/v1/workspaces/ws_demo"


class Demo:
    def __init__(self, client, batch="intake", case="de_a", tick=None):
        self.client, self.tick = client, tick
        self.case_id = f"inq_{batch}_{case}"
        self.path = f"{PREFIX}/inquiries/{self.case_id}"
        value = self.get("")
        if not value.get("simulation") or value.get("demoBatch") != batch or value.get("demoScenario") not in ("de_a", "de_b", "de_c"):
            raise RuntimeError("仅可处理 seed.py 创建的德国模拟项目")
        if value.get("activeRunId") or value.get("pendingRunId"):
            raise RuntimeError("项目有进行中或待回答任务，请先在界面完成该任务")

    @staticmethod
    def result(response):
        if response.is_error:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:1800]}")
        return response.json()

    def get(self, route):
        return self.result(self.client.get(self.path + route))

    def post(self, route, body=None, **kwargs):
        if not kwargs:
            kwargs["json"] = body or {}
        return self.result(self.client.post(self.path + route, **kwargs))

    def listing(self, group):
        return self.get("/" + group)["items"]

    def latest(self, kind):
        return max((a for a in self.listing("artifacts") if a["kind"] == kind), key=lambda a: a["version"], default=None)

    def save(self, kind, content, title=None):
        old = self.latest(kind)
        if old and old["content"] == content:
            return old
        if old:
            return self.post(f"/artifacts/{old['id']}/versions", {"baseVersion": old["version"], "content": content, "reason": "依据当前来源维护草稿"})
        return self.post("/artifacts", {"kind": kind, "title": title or kind, "content": content})

    def evidence(self, key):
        file = next(f for f in PACK["files"] if f["key"] == key)
        path = PACK_ROOT / file["file"]
        existing = next((e for e in self.listing("evidence") if e["title"].removesuffix("【模拟】") == path.name and e["sourceRole"] == file["role"]), None)
        if existing:
            return existing["id"]
        value = self.post("/evidence", files={"file": (path.name, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")}, data={"sourceRole": file["role"]})
        return value["id"]

    def offer(self, key):
        source = self.evidence("offer_" + key)
        existing = next((o for o in self.listing("supplier-offers") if o["evidenceSourceId"] == source), None)
        if existing:
            return existing
        source_offer = next(o for o in PACK["offers"] if o["key"] == key)
        return self.post("/supplier-offers", {**source_offer, "evidenceSourceId": source, "notes": "供应商原件字段；localCny 为内部国内费用分摊"})

    def wait(self, run):
        deadline = time.monotonic() + 90
        while run["status"] in ("queued", "running"):
            if self.tick:
                self.tick()
            else:
                time.sleep(0.5)
            run = self.result(self.client.get(f"{PREFIX}/runs/{run['id']}"))
            if time.monotonic() > deadline:
                raise RuntimeError(f"Run {run['id']} 仍在执行，请检查 Worker；未重复提交")
        if run["status"] != "succeeded":
            raise RuntimeError(f"Run 未成功：{json.dumps(run, ensure_ascii=False)}")
        print(f"Run {run['id']}: succeeded / revision {run.get('outputRevision')}", flush=True)
        return run

    def job(self, kind, goal, **body):
        return self.wait(self.post("/jobs", {"kind": kind, "goal": goal, **body}))

    @staticmethod
    def terms(offer):
        return {"incoterm": "FOB", "namedPlace": "Ningbo", "incotermsVersion": "2020", "paymentTerms": "30% deposit, 70% before shipment", "validUntil": "2026-11-14", "sampleTime": "7 days" if offer["packagingCny"] == "5" else "5 days", "productionTime": f"{offer['leadDays']} days after final approval and payment conditions", "pendingReconfirmation": False, "simulation": True}

    def quote(self, color=False):
        if any(c["status"] not in ("applied", "rejected", "cancelled") for c in self.listing("change-sets")):
            raise RuntimeError("请先完成当前变更，避免新核价改变其基线版本")
        offer = self.offer("a2" if color else "a1")
        old = self.latest("quotation")
        if old and old["content"].get("selectedSupplierOfferId") != offer["id"] and not color:
            raise RuntimeError("当前已经进入新版报价，请勿用首次报价覆盖；重演可新建批次")
        revisions = self.listing("revisions")
        revision_quote = (max(revisions, key=lambda r: r["number"]).get("quote") or {}) if revisions else {}
        if not old or old["content"].get("selectedSupplierOfferId") != offer["id"] or not old["content"].get("quote") or revision_quote.get("unitPriceMinor") != (921 if color else 869):
            self.job("prepare_quote", "按已收到原件核算3000件背包报价，FOB宁波，不承诺45天到港。", selectedSupplierOfferId=offer["id"], costInputs={"exchangeRate": "7.2", "margin": "20", "quantity": 3000}, inputRefs=[self.evidence("spec2" if color else "spec1"), offer["evidenceSourceId"]], sourceVersionIds=[f"demo_knowledge_{w['key']}:v1" for w in PACK["wiki"][1:4]])
        spec = self.save("spec", PACK["spec2" if color else "spec1"])
        rfq = self.latest("rfq")
        self.save("rfq", {**rfq["content"], "requiredSpecVersion": spec["id"], "packaging": spec["content"]["packaging"]})
        quote = self.latest("quotation")
        updated = self.save("quotation", {**quote["content"], **self.terms(offer)})
        for artifact in (spec, updated):
            check = self.post(f"/artifacts/{artifact['id']}/validate")
            if check["status"] != "passed":
                raise RuntimeError(str(check))
        print("报价草稿：", json.dumps(updated["content"]["quote"], ensure_ascii=False), flush=True)
        return updated

    def change(self):
        if not self.latest("quotation"):
            raise RuntimeError("请先执行 --step quote")
        source = self.evidence("change")
        offer = self.offer("a2")
        change = next((c for c in reversed(self.listing("change-sets")) if c.get("sourceId") == source and c["status"] != "rejected"), None)
        if not change:
            change = self.post("/change-sets", {"instruction": "包装从普通纸盒改为定制彩盒；包装成本2元改为5元，请联动维护规格、询价、成本、报价。", "sourceId": source})
        if change["status"] == "applied":
            return self.quote(color=True)
        if not change.get("regeneratedByRunId"):
            self.wait(self.post(f"/change-sets/{change['id']}/regenerate"))
            change = self.get(f"/change-sets/{change['id']}")
        from seed import price_quote
        cost = {"base": offer["baseCny"], "packaging": offer["packagingCny"], "local": offer["localCny"], "exchangeRate": "7.2", "margin": "20", "quantity": 3000}
        edits = {}
        for identifier in change["candidateArtifactIds"]:
            artifact = self.get(f"/artifacts/{identifier}")
            existing = next((a for a in self.listing("artifacts") if a.get("basedOnId") == identifier), None)
            if existing:
                edits[artifact["kind"]] = existing
                continue
            kind = artifact["kind"]
            content = {**artifact["content"], "pendingReconfirmation": False, "simulation": True, "sourceEvidenceIds": [source, offer["evidenceSourceId"]]}
            if kind == "spec":
                content.update(PACK["spec2"])
            elif kind == "rfq":
                content.update(packaging=PACK["spec2"]["packaging"], requiredSpecVersion=self.evidence("spec2"))
            elif kind == "cost":
                content.update(input=cost, result=price_quote(cost), selectedSupplierOfferId=offer["id"], missingFields=[])
            elif kind == "quotation":
                content.update(self.terms(offer))
                content.update(quote=price_quote(cost), selectedSupplierOfferId=offer["id"], missingFields=["shippingSchedule"])
            elif kind == "comparison":
                content.update(supplierOffers=self.listing("supplier-offers"), selectedSupplierOfferId=offer["id"], missingFields=[])
            else:
                raise RuntimeError(f"已有下游 {kind} 成果，请在界面复核本次变更，辅助脚本不自动替你处理")
            edits[kind] = self.post(f"/artifacts/{identifier}/versions", {"baseVersion": artifact["version"], "content": content})
        mapping = {"draft_spec_pack": "spec", "extract_bag_requirements": "spec", "build_supplier_rfq": "rfq", "normalize_quotes": "comparison", "calculate_cost": "cost", "draft_quotation": "quotation"}
        actions = self.get(f"/change-sets/{change['id']}/node-actions")["items"]
        for impact in change["nodeImpacts"]:
            node = impact["nodeKey"]
            if any(a["nodeKey"] == node and a["action"] in ("edit", "no_impact") for a in actions):
                continue
            artifact = edits.get(mapping.get(node))
            if not artifact and impact["impactType"] == "direct":
                raise RuntimeError(f"直接影响节点 {node} 请在界面处理")
            body = {"nodeKey": node, "action": "edit" if artifact else "no_impact", "reason": "按彩盒客户来信及工厂A新版报价维护，模拟操作者复核" if artifact else "尚未执行此下游阶段，没有既存成果需修订；后续须以彩盒新版规格建立样品、PO和生产资料"}
            if artifact:
                body["targetArtifactVersionId"] = artifact["id"]
            self.post(f"/change-sets/{change['id']}/node-actions", body)
        self.post(f"/change-sets/{change['id']}/activate")
        # Run the actual costing node again, so the latest business revision also carries 9.21.
        self.job("prepare_quote", "按彩盒新版核算3000件背包报价", selectedSupplierOfferId=offer["id"], costInputs=cost, inputRefs=[self.evidence("spec2"), offer["evidenceSourceId"]], sourceVersionIds=[f"demo_knowledge_{w['key']}:v1" for w in PACK["wiki"][1:4]])
        return self.quote(color=True)

    def order(self):
        from seed import production_templates
        quote = self.latest("quotation")
        if not quote or quote["content"].get("selectedSupplierOfferId") != self.offer("a2")["id"]:
            raise RuntimeError("PO使用彩盒新版，请先完成 --step change")
        refs = [self.evidence(k) for k in ("po", "customer_ok", "seller_ok", "supplier_ok", "payment", "sample_check")]
        if not self.latest("pi"):
            self.job("confirm_order", "核对3000件背包PO与彩盒新版报价，制作PI草稿，批准另行登记", inputRefs=refs)
        if not self.latest("production"):
            self.job("prepare_production", "根据彩盒最终规格准备3000件背包生产资料草稿，不自动放行", inputRefs=refs)
        for kind, content in production_templates(self.case_id, PACK).items():
            self.save(kind, {**content, "sourceEvidenceIds": refs}, {"pi": "PI 草稿", "production": "生产指令草稿", "ta": "T&A 相对节点计划", "qc": "QC 检查清单"}[kind])
        print("订单与生产资料草稿已备齐；未记录任何批准。", flush=True)
        return self.check()

    def check(self):
        result = self.get("/sop-status")["productionRelease"]
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return result

    def approve(self):
        if not self.latest("production"):
            raise RuntimeError("请先执行 --step order 并核对原件")
        spec, quotation = self.latest("spec"), self.latest("quotation")
        if spec["content"].get("packaging") != PACK["spec2"]["packaging"] or quotation["content"].get("quote", {}).get("goodsSubtotalMinor") != 2763000:
            raise RuntimeError("当前规格或金额与模拟确认原件不符，请先核对，不能套用预置批准")
        customer, supplier = self.evidence("customer_ok"), self.evidence("supplier_ok")
        revision = str(self.get("")["currentRevision"])
        for scope, target, refs in [("customer_spec_approval", spec["id"], [customer]), ("commercial_quotation_approval", quotation["id"], []), ("supplier_production_confirmation", revision, [supplier])]:
            if not any(a["scope"] == scope and a.get("targetVersionId") == target and a["decision"] == "approved" for a in self.listing("approvals")):
                self.post("/approvals", {"scope": scope, "targetVersionId": target, "decision": "approved", "evidenceRefs": refs, "note": "演示操作者显式执行 approve；依据模拟原件的演练批准，不是真实交易"})
        if not any(s.get("customerApproved") and s.get("specVersionId") == spec["id"] for s in self.listing("samples")):
            self.post("/samples", {"specVersionId": spec["id"], "customerApproved": True, "evidenceSourceId": customer, "simulation": True})
        po = self.evidence("po")
        if not any(o.get("documentVersionId") == po and o.get("buyerConfirmed") and o.get("sellerConfirmed") for o in self.listing("order-confirmations")):
            self.post("/order-confirmations", {"documentVersionId": po, "buyerConfirmed": True, "sellerConfirmed": True, "buyerEvidenceSourceId": customer, "sellerEvidenceSourceId": self.evidence("seller_ok"), "simulation": True})
        if not any(p.get("decision") == "verified" for p in self.listing("payment-assurance-checks")):
            self.post("/payment-assurance-checks", {"decision": "verified", "evidenceSourceId": self.evidence("payment"), "verificationBasis": "模拟核验 DEMO-PAY-DE-001：PO总额USD27630，30%定金USD8289；非银行真实到账", "method": "manual_demo_review", "simulation": True})
        return self.check()

    def release(self):
        revision = self.get("")["currentRevision"]
        pack = next((p for p in reversed(self.listing("production-packs")) if p["manifest"]["revision"] == revision), None)
        if not pack:
            artifacts = [self.latest(k)["id"] for k in ("spec", "quotation", "pi", "production", "ta", "qc") if self.latest(k)]
            pack = self.post("/production-packs", {"revision": revision, "artifactVersionIds": artifacts, "simulation": True})
        check = self.post(f"/production-packs/{pack['id']}/validate")
        if check["status"] != "passed":
            raise RuntimeError(json.dumps(check, ensure_ascii=False))
        if not pack["released"]:
            pack = self.post(f"/production-packs/{pack['id']}/release")
        print(f"模拟资料包已放行：{pack['id']}；不代表工厂实际开工。", flush=True)
        return pack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", default="intake")
    parser.add_argument("--case", choices=["de_a", "de_b", "de_c"], default="de_a")
    parser.add_argument("--step", choices=["quote", "change", "order", "check", "approve", "release"], required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9_-]{1,32}", args.batch) or urlparse(args.url).hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("仅允许本机演示服务和合法批次名称")
    env = local_env()
    if env.get("APP_ENV") != "demo":
        parser.error("仅允许 APP_ENV=demo")
    with httpx.Client(base_url=args.url, timeout=35, trust_env=False) as client:
        Demo.result(client.post("/api/v1/auth/session", json={"email": env.get("DEMO_EMAIL", "demo@navowork.local"), "password": env.get("DEMO_PASSWORD", "ChangeMe123!")}))
        getattr(Demo(client, args.batch, args.case), args.step)()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, httpx.HTTPError) as exc:
        raise SystemExit(str(exc))
