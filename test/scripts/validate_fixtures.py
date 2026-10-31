"""Check actual source files, hashes, locators, math, scopes, versions and gates."""
from pathlib import Path
from hashlib import sha256
from decimal import Decimal, ROUND_UP
from email import policy
from email.parser import BytesParser
import json, sys
import re
from openpyxl import load_workbook
from pypdf import PdfReader
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
errors=[]
def check(ok,msg):
    if not ok: errors.append(msg)
def readj(p): return json.loads(p.read_text(encoding="utf-8"))

case_files=sorted((ROOT/"cases").glob("*.json"))
check(len(case_files)==3,"expected 3 case JSON files")
cases=[readj(p) for p in case_files]
byid={c["case"]["id"]:c for c in cases}
check(set(byid)=={"BAG-2026-DE-001","BAG-2026-DE-002","BAG-2026-DE-003"},"case ids do not match the three independent inputs")
source_index={}
for case in cases:
    cid=case["case"]["id"]
    check(case["case"].get("all_values_simulated") is True,"case not marked simulated: "+cid)
    for src in case["sources"]:
        p=ROOT/"inputs"/cid/src["name"]
        check(p.is_file(),f"missing source: {p}")
        if not p.is_file(): continue
        digest=sha256(p.read_bytes()).hexdigest()
        check(src.get("sha256")==digest,f"source SHA-256 mismatch: {cid}/{src['name']}")
        check(src.get("simulated") is True,f"source not marked simulated: {cid}/{src['name']}")
        source_index[src["id"]]=(case,src,p)
        for loc in src.get("locators",[]):
            kind=loc.get("type")
            if kind=="eml":
                raw=p.read_bytes().decode("utf-8",errors="replace")
                msg=BytesParser(policy=policy.default).parsebytes(p.read_bytes())
                if loc.get("body_quote"): check(loc["body_quote"] in raw,f"email quote not found: {cid}/{src['name']}")
                if loc.get("header")=="Subject": check(msg.get("Subject") is not None,"email subject missing")
                if loc.get("message_id"): check(msg.get("Message-ID")==loc["message_id"],f"message-id mismatch: {src['name']}")
            elif kind=="xlsx":
                wb=load_workbook(p,data_only=False,read_only=True)
                check(loc.get("sheet") in wb.sheetnames,f"xlsx sheet missing: {loc}")
                if loc.get("sheet") in wb.sheetnames:
                    ws=wb[loc["sheet"]]
                    check(ws[loc["cell"]].value is not None,f"xlsx cell empty: {loc}")
                wb.close()
            elif kind=="pdf":
                reader=PdfReader(str(p))
                check(1<=loc.get("page",0)<=len(reader.pages),f"PDF locator page invalid: {loc}")
                if 1<=loc.get("page",0)<=len(reader.pages) and loc.get("field"):
                    text=re.sub(r"\s+"," ",reader.pages[loc["page"]-1].extract_text() or "").casefold()
                    label=re.sub(r"\s+"," ",loc["field"]).casefold()
                    check(label in text,f"PDF locator field label not found on page: {loc}")
            elif kind=="image":
                with Image.open(p) as image: check(image.width>0 and image.height>0,"empty image source")
            else: check(False,f"unsupported locator type {kind}: {src['name']}")

    # Source references in assertions and resolutions must be local to their Case.
    source_ids={s["id"] for s in case["sources"]}
    sources_by_id={s["id"]:s for s in case["sources"]}
    for assertion in case.get("assertions",[]):
        check(assertion.get("case_id")==cid,f"assertion case mismatch {assertion.get('id')}")
        sid=assertion.get("source_id")
        check(sid in source_ids,f"assertion source is missing/cross-case: {assertion.get('id')}")
        locator=assertion.get("source_locator")
        if sid in sources_by_id:
            source_record=sources_by_id[sid]
            declared=source_record.get("locators",[])
            def locator_matches(item):
                for key,value in locator.items():
                    if key=="body_quote":
                        if not isinstance(item.get(key),str) or value not in item[key]: return False
                    elif item.get(key)!=value: return False
                return True
            check(any(locator_matches(item) for item in declared),f"assertion locator is not declared for its source: {assertion.get('id')}")
            sp=ROOT/"inputs"/cid/source_record["name"]
            if locator and locator.get("type")=="eml" and locator.get("body_quote"):
                check(locator["body_quote"] in sp.read_bytes().decode("utf-8",errors="replace"),f"assertion email quote is not in source: {assertion.get('id')}")
            elif locator and locator.get("type")=="pdf" and locator.get("body_quote"):
                page=locator.get("page",1)-1
                reader=PdfReader(str(sp))
                content=re.sub(r"\s+"," ",reader.pages[page].extract_text() or "")
                quote=re.sub(r"\s+"," ",locator["body_quote"])
                check(quote.casefold() in content.casefold(),f"assertion PDF quote is not on its page: {assertion.get('id')}")
            elif locator and locator.get("type")=="xlsx":
                book=load_workbook(sp,data_only=True,read_only=True)
                cell=book[locator["sheet"]][locator["cell"]].value
                book.close()
                value=assertion.get("value",{}).get("value",{})
                if isinstance(value,dict) and "amount" in value:
                    check(Decimal(str(cell))==Decimal(value["amount"]),f"assertion XLSX value differs from cited cell: {assertion.get('id')}")
        val=assertion.get("value",{})
        if val.get("kind")=="unknown":
            check(bool(val.get("reason")),f"unknown lacks reason: {assertion.get('id')}")
            check(assertion.get("status")=="unknown",f"unknown status mismatch: {assertion.get('id')}")
    assertion_ids={a["id"] for a in case.get("assertions",[])}
    for resolution in case.get("resolutions",[]):
        check(resolution.get("assertion_id") in assertion_ids,f"resolution assertion missing: {cid}/{resolution}")
        ev=resolution.get("approved_evidence_id")
        check(ev is None or ev in source_ids,f"resolution evidence missing/cross-case: {cid}/{resolution}")

main=byid.get("BAG-2026-DE-001",{})
expected=main.get("expected",{})
q=expected.get("quote_math",{})
def cent(v): return (Decimal(v)/Decimal("7.20")/Decimal("0.80")).quantize(Decimal("0.01"),rounding=ROUND_UP)
check(cent("50")==Decimal("8.69") and cent("52")==Decimal("9.03") and cent("53")==Decimal("9.21"),"independent Decimal golden calculation mismatch")
check(q.get("supplier_a_v1",{}).get("unit_usd")=="8.69","oracle V1 unit price mismatch")
check(q.get("supplier_b",{}).get("unit_usd")=="9.03","oracle supplier B unit price mismatch")
check(q.get("supplier_a_v2",{}).get("unit_usd")=="9.21","oracle V2 unit price mismatch")
check(q.get("supplier_a_v1",{}).get("total_usd")=="26070.00","oracle V1 total mismatch")
check(q.get("supplier_b",{}).get("total_usd")=="27090.00","oracle supplier B total mismatch")
check(q.get("supplier_a_v2",{}).get("total_usd")=="27630.00","oracle V2 total mismatch")
check(q.get("supplier_a_v2",{}).get("delta_unit_usd")=="0.52","oracle unit delta mismatch")
check(q.get("supplier_a_v2",{}).get("delta_total_usd")=="1560.00","oracle total delta mismatch")
gold=readj(ROOT/"expected"/"quote-golden.json")
check(gold.get("results")==q,"standalone expected quote oracle differs from main Case oracle")
check(gold.get("assumptions",{}).get("fx_cny_per_usd")=="7.20" and gold.get("assumptions",{}).get("target_gross_margin")=="0.20","quote oracle assumptions missing or inconsistent")

xlsx=ROOT/"inputs"/"BAG-2026-DE-001"/"factory-A-quote.xlsx"
wf=load_workbook(xlsx,data_only=False,read_only=True); ws=wf["Factory A Quote"]
wv=load_workbook(xlsx,data_only=True,read_only=True); wsv=wv["Factory A Quote"]
check([ws[f"B{r}"].value for r in (10,11,12,14,15)]==[44,2,4,1000,28],"XLSX actual price/MOQ/lead values do not match oracle")
check(ws["B13"].value=="=SUM(B10:B12)","XLSX cost basis formula missing or changed")
check(Decimal(str(wsv["B13"].value))==Decimal("50"),"XLSX calculated CNY 50.00 basis is not cached/available")
wf.close(); wv.close()

art=expected.get("artifacts",[]); aids={a["id"] for a in art}
check("production-pack-v1-draft" in aids,"production pack referenced by gate/approval is missing")
check(all(a.get("immutable") is True for a in art),"an artifact snapshot is not marked immutable")
versions={a["id"]:a for a in art}
for artifact in art:
    check(bool(artifact.get("content_hash")),f"artifact version hash missing: {artifact['id']}")
    unhashed={k:v for k,v in artifact.items() if k!="content_hash"}
    computed=sha256(json.dumps(unhashed,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
    check(artifact.get("content_hash")==computed,f"artifact content hash mismatch: {artifact['id']}")
deps=expected.get("artifact_dependencies",[])
check(len(deps)>=3,"artifact dependency graph is incomplete")
for dep in deps:
    check(dep.get("downstream_version_id") in versions,f"dependency downstream version missing: {dep}")
    check(dep.get("upstream_version_id") in versions,f"dependency upstream version missing: {dep}")
    check(bool(dep.get("field_paths")),f"dependency has no affected field paths: {dep}")
check(len(expected.get("diffs",[]))>=3,"fewer than three impacted artifact diffs")
check(len({d["artifact_id"] for d in expected.get("diffs",[])})>=3,"diffs do not cover three distinct artifacts")
for app in expected.get("approvals",[]):
    check(app.get("target_version_id") in aids,f"approval target missing: {app.get('id')}")
    if app.get("target_version_id") in versions:
        check(app.get("target_version_hash")==versions[app["target_version_id"]].get("content_hash"),f"approval is not bound to exact version hash: {app.get('id')}")
    ev=app.get("evidence_source_id")
    check(ev is None or ev in {s["id"] for s in main.get("sources",[])},f"approval evidence missing/cross-case: {app.get('id')}")
gates={g["name"]:g for g in expected.get("gates",[])}
check(gates.get("quote_release_v2",{}).get("decision")=="deny","V2 quote release should be denied")
check(len(gates.get("quote_release_v2",{}).get("blocking_reasons",[]))>=2,"V2 quote gate does not show supplier confirmation blockers")
check(gates.get("production_release_v2",{}).get("decision")=="deny","production gate should be denied")
check({"physical sample approval missing","production owner confirmation missing"}.issubset(set(gates.get("production_release_v2",{}).get("blocking_reasons",[]))),"production gate lacks sample/owner blockers")
check(all(d.get("real_connection") is False and d.get("sent_at") is None for d in expected.get("deliveries",[])),"delivery falsely marked sent or connected")

scenario_doc=readj(ROOT/"scenarios"/"demo-scenarios.json")
scenario_ids=[s["id"] for s in scenario_doc.get("scenarios",[])]
check(len(scenario_ids)==25 and len(set(scenario_ids))==25,"scenario list must contain exactly 25 unique cases")
check(set([f"E{i:02d}" for i in range(1,8)]+[f"N{i:02d}" for i in range(1,8)]).issubset(scenario_ids),"PRD scenario IDs E01-E07 and N01-N07 missing")
check(scenario_doc.get("count")==25,"scenario count field mismatch")
scenario_map={s["id"]:s["maps_to"] for s in scenario_doc.get("scenarios",[])}
for sid in [f"E{i:02d}" for i in range(1,8)]+[f"N{i:02d}" for i in range(1,8)]:
    check(scenario_map.get(sid)==f"PRD 12.{1 if sid[0]=='E' else 2} {sid}",f"PRD scenario mapping is incorrect: {sid}")
check("PRD 12.1 E09" not in json.dumps(scenario_doc,ensure_ascii=False),"scenario map incorrectly uses a nonexistent PRD 12.1 E09 ID")
check("prompt-injection.eml" in json.dumps(scenario_doc,ensure_ascii=False),"scenario coverage missing prompt-injection input")
check("BAG-2026-DE-002" in json.dumps(scenario_doc,ensure_ascii=False),"scenario coverage missing cross-case input")
check("sent_at" in json.dumps(scenario_doc,ensure_ascii=False),"scenario coverage missing unsent-state check")
adv_records=scenario_doc.get("adversarial_sources",[])
check(len(adv_records)==1,"adversarial source hash record missing")
if adv_records:
    advpath=ROOT/"inputs"/"adversarial"/adv_records[0]["name"]
    check(sha256(advpath.read_bytes()).hexdigest()==adv_records[0].get("sha256"),"adversarial source hash mismatch")
check(len(expected.get("stage_snapshots",[]))==2,"explicit before/after supplier-price stage snapshots missing")
if expected.get("stage_snapshots"):
    before=expected["stage_snapshots"][0]
    check(before.get("id")=="before-supplier-color-box-price","first stage snapshot does not represent missing-price phase")
    update_id="src-bag-2026-de-001-factory-a-color-box-update"
    check(update_id not in before.get("source_ids",[]),"missing-price stage incorrectly contains the supplier price update")
    check("custom color-box price is unknown" in before.get("quote_release",{}).get("blocking_reasons",[]),"missing-price stage lacks quote blocker")
check(expected.get("po_diff",{}).get("against_version_id")=="quote-v1","PO diff must compare against the approved V1 version")
check(len(expected.get("po_diff",{}).get("differences",[]))>=3,"PO diff lacks expected business-field mismatches")
manifest=expected.get("export_snapshot",{})
manifest_sources={s["id"]:s["sha256"] for s in main.get("sources",[])}
check(manifest.get("case_id")==main.get("case",{}).get("id"),"export snapshot Case mismatch")
check(manifest.get("sent_at") is None and manifest.get("real_export_created") is False,"expected export manifest implies an actual send/export")
check(manifest.get("quantity")=={"amount":"3000","unit":"piece"},"export snapshot quantity mismatch")
for snap in manifest.get("source_snapshots",[]):
    check(manifest_sources.get(snap.get("id"))==snap.get("sha256"),f"export source snapshot hash mismatch: {snap.get('id')}")
for snap in manifest.get("artifact_versions",[]):
    check(versions.get(snap.get("id"),{}).get("content_hash")==snap.get("content_hash"),f"export artifact version snapshot mismatch: {snap.get('id')}")

adversarial=ROOT/"inputs"/"adversarial"/"prompt-injection.eml"
check(adversarial.exists() and "attacker@external.invalid" in adversarial.read_text(encoding="utf-8"),"adversarial email fixture missing/invalid")
if errors:
    print("FAIL")
    for e in errors: print(" -",e)
    sys.exit(1)
print(f"Fixture consistency check passed: {len(cases)} cases, {sum(len(c['sources']) for c in cases)} hash-verified sources, 25 scenario definitions, XLSX source locators/prices/formula, Decimal totals, version/approval scopes and release gates.")
