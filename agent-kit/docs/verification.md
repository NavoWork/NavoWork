# Verification record

Date: 2026-10-31, Asia/Shanghai. Host source baseline: `origin/lirui@5fcf0a1`; merged into `justike` as `4e34ce0`. This record describes standalone Agent Kit validation, not completed workbench integration.

## Executed checks

| Level | Actual result | Evidence / scope |
| --- | --- | --- |
| Contracts, deterministic tools, readers, formulas | Passed | Shared behavioral tests for local adapter and host DTO/service substitute; the same file ToolService creates files against both. Actual Office/PDF inputs, source hashes/locators, strict pricing, unknowns/MOQ, immutable versions, CAS, idempotency, scope, partial export retry, manual-note preservation, manual-field conflict and client ZIP isolation. |
| Offline graph/tool loop | Passed | Real LangGraph graph, typed tool binding and ToolMessage feedback with explicitly scripted model doubles. Missing price drafts precede pause. Two separate Python processes close/reopen SQLite checkpoints and continue the same Job without duplicating existing versions. Hypothesis/negation tests verify the double's nonmutating path, not real model semantic competence. |
| Full standalone suite | **31 passed, 1 skipped; 5 subtests passed** | `python -m pytest agent-kit/tests -q`, 21.10 seconds in this environment. The skipped test is real-model acceptance. |
| External offline file replay | Passed | `python agent-kit/scripts/replay.py --output agent-kit/output/replay-20261031-verified`: 12 real generated files across initial, pending-price and supplemented snapshots. Tool context never receives the oracle. Old version bytes remain unchanged. |
| Monetary checks | Passed offline | A: USD 8.69 / 26,070.00; B: USD 9.03 / 27,090.00; new A packaging: USD 9.21 / 27,630.00. Reopened actual cost XLSX caches and customer PDF/XLSX match. FX 7.20 and gross-margin ratio 0.20 are explicit host fixture decisions. |
| PDF visual | Passed for three replay quotations | Poppler PNG rendering, all three one-page images viewed. Initial CID substitution caused broken English spacing; changed to Helvetica for Latin content, then regenerated and reinspected all pages. V2 shows Pending pricing / Unknown amounts. V1/V3 amounts and versions agree. Poppler emits missing Symbol/ArialUnicode display-font warnings, but generated Latin quotation glyphs render correctly. |
| DOCX/XLSX structural | Passed | Reopened actual DOCX paragraphs/tables and XLSX values/formulas/caches. This is not a visual review. |
| DOCX/XLSX visual | Not executed | Word is not registered; LibreOffice is absent from PATH. No claim of arbitrary Office layout fidelity. |
| Real model | **Not executed** | No MODEL_API_KEY/MODEL_NAME configured. Live tests skip explicitly. CLI returns MODEL_NOT_CONFIGURED, live_executed=false and exit 2. Scripted models always report offline_model_double. |
| Packaging | Passed | A wheel builds with `pip wheel --no-index --no-deps --no-build-isolation ./agent-kit`. Product Skills are included as package resources. |
| FastAPI / real host / frontend | Not yet executed | M5 remains separate. A DTO/service substitute is not real host contract acceptance. |

The replay report, actual files, source manifests, full referenced tool results and events live under the explicitly retained (Git-ignored) `agent-kit/output/replay-20261031-verified/`. Golden expectations are read only by the external harness. The later price email first enters the third stage; `test/core15/` is never imported.

## Reproduction

Use README installation and commands. Replay output must be a fresh directory. To render all quotation PDFs:

```powershell
New-Item -ItemType Directory -Force agent-kit/output/my-replay/qa | Out-Null
Get-ChildItem agent-kit/output/my-replay/files -Filter *.pdf | ForEach-Object {
  pdftoppm -scale-to 1400 -png -singlefile $_.FullName (Join-Path (Resolve-Path agent-kit/output/my-replay/qa) $_.BaseName)
}
```

## Remaining acceptance

Real-model source interpretation, hypothetical/negative intent behavior, live missing-price recovery, and injection resistance remain unaccepted until run with an actual configured model. Function tests do not establish those abilities. Full Case 002/003 semantic interpretation is also a live acceptance concern; current offline tests check actual input readability, unknown-fee preservation, MOQ blocking and isolation separately.

M5 needs real SQLAlchemy/Blob/Artifact/Run adapters, host authorization and lease/revision fencing, single-pricing integration, existing conversation/clarification event projection, fixed export manifests, and workbench verification. Parallel BOM/order/evaluation modules have separate acceptance; their existence does not mean they are registered in this runtime.

Official interface references checked because Context7 MCP was unavailable in this session:
- https://docs.langchain.com/oss/python/langgraph/quickstart
- https://docs.langchain.com/oss/python/langgraph/interrupts

Direct LangGraph/LangChain versions installed into the ignored local `.deps/` match host declarations: langgraph 1.2.19, langchain 1.4.7, langchain-openai 1.7.3, langgraph-checkpoint-sqlite 3.1.3. Bundled openpyxl 3.1.5, python-docx 1.2.0, pypdf 6.10.0 and reportlab 4.4.9 were used for file tests; host declares newer pypdf/reportlab and needs a resolved integration environment.
