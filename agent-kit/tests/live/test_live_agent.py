"""Opt-in real model smoke acceptance; no scripted model can satisfy this test."""
import os
import pytest
from navowork_agent.tools.service import ToolService
from navowork_agent.runtime.agent import agent_session
from navowork_agent.contracts import FileRef
from support import make_adapter, INPUTS


@pytest.mark.skipif(not (os.getenv("MODEL_API_KEY") and os.getenv("MODEL_NAME")), reason="Live validation not executed: model configuration absent")
def test_real_model_reads_prices_generates_validates(tmp_path):
    a = make_adapter(tmp_path)
    for name in ("inquiry.eml", "factory-A-quote.xlsx", "factory-B-quote.pdf"):
        a.import_source(INPUTS / "BAG-2026-DE-001" / name)
    with agent_session(ToolService(a), max_tools=40) as run:
        result = run(goal="Read inquiry and supplier files, prepare Factory A pricing using confirmed FX/margin in host facts. Generate spec, cost and customer quotation drafts, and validate all artifacts. Missing dimensions can remain unknown; don't ask for unavailable image OCR. Do not send or approve anything.")
    assert result["live_executed"]
    assert len(result.get("outputs", [])) >= 4, result
    names = [a._load()["results"][e["result_ref"]] for e in a._load()["events"] if e.get("result_ref")]
    events = a._load()["events"]
    summaries = " ".join(e["summary"] for e in events)
    assert all(n in summaries for n in ("read_document", "calculate_quote", "publish_documents", "validate_artifact"))
    assert any(r.get("data", {}).get("pricing", {}).get("quote", {}).get("unit_usd") == "8.69" for r in names)
