# Real research provider acceptance

These two tests use the actual configured provider and persisted Case APIs. They
do not inject provider doubles. Normal test runs skip them before provider calls.
They use a disposable demo database/storage, a synthetic tote specification, and
a locally drawn BOM labelled **SIMULATED / NOT A SUPPLIER QUOTE**. They never
upload an actual customer document.

Real provider acceptance remains open until these tests pass with the team's
chosen service. An offline pass or a skip is not evidence of working image
generation or visual recognition. The partner responsible for provider acceptance
can run the following after configuring credentials; do not commit credentials.
Requests can incur provider charges.

## Provider contract

| Test | Required environment | HTTP contract |
| --- | --- | --- |
| Concept image | `IMAGE_MODEL`, `IMAGE_API_KEY` (fallback `IMAGE_MODEL_API_KEY`, then `MODEL_API_KEY`) | `IMAGE_BASE_URL` + `/images/generations`; JSON `data[].b64_json`, PNG/JPEG |
| BOM image | `MODEL_NAME`, `MODEL_API_KEY` | `MODEL_BASE_URL` + `/chat/completions`; multimodal messages with an image data URL, JSON transcription |

Image endpoint fallback: `MODEL_BASE_URL`, `OPENAI_BASE_URL`, then
`https://api.openai.com/v1`. Vision endpoint fallback: `OPENAI_API_BASE`,
`OPENAI_BASE_URL`, then `https://api.openai.com/v1`. Select a vision-capable model
for BOM recognition. Configure image and vision URLs independently when needed.
The model name and credentials are read from the process environment; this
harness does not load `.env` files.

The currently mentioned TokenHub setup uses a Responses wire API. A
Responses-specific bridge is **not configured or verified** by these tests.
`TOKENHUB_API_KEY` is not automatically mapped to `MODEL_API_KEY`; the current
adapters require the contracts above. Do not treat a configured Responses model
as proof that Chat Completions or image generation is available.

## Run from the repository root

Use the project's Python environment with backend and Agent Kit dependencies
installed. First set the model names, approved endpoint URLs and credentials in
that shell from your normal secret store. Then, in PowerShell:

```powershell
$env:NAVOWORK_LIVE_RESEARCH = '1'
$env:PYTHONPATH = "$PWD/backend;$PWD/agent-kit/src;$PWD/agent-kit/tests"
python -m pytest backend/tests/live/test_live_research.py -q -rs -p no:cacheprovider
Remove-Item Env:NAVOWORK_LIVE_RESEARCH
```

Run one provider separately with `-k concept` or `-k bom`. Missing credentials or
model names produce an explicit skip. Once configured, API/provider failures fail
the test; they are not converted into skips. Tests do not print credentials or
remote response bodies. The BOM assertions require real nonempty transcription
and rows bound to the uploaded image hash, without assuming exact model wording
or granting price approval. The image assertions verify decodable saved bytes,
hash, same-snapshot editable DOCX with embedded image/specification, and download
authorization. They do not certify visual quality or engineering feasibility.

To verify default exclusion without any live requests:

```powershell
Remove-Item Env:NAVOWORK_LIVE_RESEARCH -ErrorAction SilentlyContinue
python -m pytest backend/tests/live/test_live_research.py -q -rs -p no:cacheprovider
```
