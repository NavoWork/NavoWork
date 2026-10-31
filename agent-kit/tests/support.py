"""OFFLINE fixture interpretation only. Never imported by the product runtime.

This adapter maps fixture labels with simple rules to exercise actual tools. It is
not an Agent and cannot establish semantic/live-model acceptance.
"""
from pathlib import Path
import re
from navowork_agent.adapters.local import LocalAdapter
from navowork_agent.contracts import ExecutionContext, Citation, Fact, ToolCall
from navowork_agent.tools.pricing import CostLine, PricingInput, ContentSnapshot
from navowork_agent.tools.service import ToolService

REPO = Path(__file__).resolve().parents[2]
INPUTS = REPO / "test" / "inputs"


def make_adapter(tmp_path, case="BAG-2026-DE-001"):
    a = LocalAdapter(tmp_path, ExecutionContext(case_id=case, job_id="j_quote", run_id="r_test"))
    a.update_user_facts({"fx": "7.20", "margin": "0.20"}, supersede=False)
    return a


def invoke(service, name, arguments=None, key=None):
    from navowork_agent.contracts import digest
    arguments = arguments or {}
    return service.call(ToolCall(tool_call_id="tc", name=name, arguments=arguments,
                                idempotency_key=key or digest([name, arguments])))


def citation(adapter, ref, *, cell=None, part=None, page=None, excerpt=None):
    sections = adapter.read_document(ref.file_id)["sections"]
    section = next(s for s in sections if (cell is None or s["locator"].get("cell") == cell)
                   and (part is None or s["locator"].get("part") == part)
                   and (page is None or s["locator"].get("page") == page))
    return Citation(file_id=ref.file_id, sha256=ref.sha256, locator=section["locator"], excerpt=excerpt or section["text"][:3000])


def base_snapshot(adapter, supplier="A", input_root=None):
    root = input_root or INPUTS / "BAG-2026-DE-001"
    inquiry = adapter.import_source(root / "inquiry.eml")
    q = citation(adapter, inquiry, part="body")
    quantity = int(re.search(r"([\d,]+) custom backpacks", q.excerpt).group(1).replace(",", ""))
    if supplier == "A":
        ref = adapter.import_source(root / "factory-A-quote.xlsx")
        sections = adapter.read_document(ref.file_id)["sections"]
        costs = []
        for label, cell in [("base", "B10"), ("packaging", "B11"), ("local", "B12")]:
            s = next(s for s in sections if s["locator"]["cell"] == cell)
            costs.append(CostLine(category=label, amount=Fact(value=str(s["value"]), sources=[citation(adapter, ref, cell=cell)]), scope="per_unit"))
        moq = next(s["value"] for s in sections if s["locator"]["cell"] == "B14")
        m = Fact(value=moq, sources=[citation(adapter, ref, cell="B14")])
        packaging = Fact(value="ordinary paper box", sources=[citation(adapter, ref, cell="C11")])
    else:
        ref = adapter.import_source(root / "factory-B-quote.pdf")
        cite = citation(adapter, ref, page=1)
        costs = []
        for cat, label in [("base", "Base manufacturing"), ("packaging", "Standard packaging"), ("local", "Allocated local charges")]:
            amount = re.search(re.escape(label) + r"\s+CNY ([\d.]+)", cite.excerpt).group(1)
            costs.append(CostLine(category=cat, amount=Fact(value=amount, sources=[cite]), scope="per_unit"))
        moq = int(re.search(r"MOQ\s+([\d,]+)", cite.excerpt).group(1).replace(",", ""))
        m = Fact(value=moq, sources=[cite])
        packaging = Fact(value="ordinary paper box", sources=[cite])
    return ContentSnapshot(fields={"product": Fact(value="custom backpacks", sources=[q]), "quantity": Fact(value=quantity, sources=[q]),
        "packaging": packaging, "material": Fact(value=None), "dimensions": Fact(value=None),
        "incoterm": Fact(value="FOB", sources=[q]), "named_place": Fact(value="Ningbo", sources=[q]),
        "requested_arrival": Fact(value="Hamburg within 45 days if feasible", sources=[q])},
        pricing=PricingInput(quantity=quantity, costs=costs, fx_cny_per_usd=Fact(value="7.20", user_fact="fx"),
            target_gross_margin=Fact(value="0.20", user_fact="margin"), moq=m), supplier=f"Factory {supplier}",
        internal_notes={"private": "INTERNAL_COST_MARGIN_DO_NOT_EXPORT"})


def change_snapshot(adapter, snapshot, *, priced=False):
    change = adapter.import_source(INPUTS / "BAG-2026-DE-001" / "change-color-box.eml")
    fields = dict(snapshot.fields)
    fields["packaging"] = Fact(value="custom printed color box", sources=[citation(adapter, change, part="body")])
    amount = Fact(value=None)
    if priced:
        update = adapter.import_source(INPUTS / "BAG-2026-DE-001" / "factory-A-color-box-update.eml")
        c = citation(adapter, update, part="body")
        value = re.search(r"color box is CNY ([\d.]+)", c.excerpt).group(1)
        amount = Fact(value=value, sources=[c])
    costs = [c.model_copy(update={"amount": amount}) if c.category == "packaging" else c for c in snapshot.pricing.costs]
    return snapshot.model_copy(update={"fields": fields, "pricing": snapshot.pricing.model_copy(update={"costs": costs, "moq": Fact(value=None)}),
        "internal_notes": {**snapshot.internal_notes, "supplier_question": "Please confirm color-box price, MOQ, sample and production lead time; 45-day arrival is unconfirmed."}})


def baselines(adapter):
    versions = {a["ref"]["kind"]: a["ref"]["version"] for a in adapter.list_artifacts()}
    return {kind: versions.get(kind, 0) for kind in ("spec", "cost", "quotation")}


def publish(service, snapshot, intent="initial", key=None, bases=None):
    return invoke(service, "publish_documents", {"snapshot": snapshot.model_dump(mode="json"),
        "baselines": bases if bases is not None else baselines(service.adapter), "intent": intent}, key)
