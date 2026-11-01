# Workbench demo fixture audit

**Review type:** static code/data review only. No demo import, API call, or runtime behavior was exercised.

## Findings

### 1. The pack-count and carton dimensions are physically incompatible

`demo/workbench_v2/wiki/case-nordlicht-confirmation.md` lines 28–29 specifies an individual color box of 32 × 47 × 17 cm and 20 pieces per 60 × 45 × 50 cm outer carton. The 20 inner boxes have a combined volume of 511,360 cm³; the outer carton volume is 135,000 cm³. The inner boxes exceed outer-carton volume by about 3.79× before allowing for packing clearances or carton walls, so these values cannot describe one packing configuration. The inquiry also asks for 20 pcs/carton (`sources/de-inquiry.eml`, line 15), and the PO repeats 20 pcs/carton (`sources/po-de-001.txt`, line 13), making the count a repeated source claim rather than an isolated wiki typo.

Keep these values together only as a clearly labeled **packaging-conflict exercise**. Preserve each source statement as observed, mark the packaging configuration unresolved, and do not present a corrected carton plan as customer- or supplier-confirmed. For an unambiguous walkthrough, use a separate case with its own case ID and source set. The core15 package demonstrates a distinct viable configuration: a 46 × 33 × 8 cm box, five per 48 × 35 × 42 cm carton (`test/scripts/core15_content.json`, supplier and PO entries; `test/core15/manifest.json`, case `BAG-2026-DE-001`).

### 2. Payment terms disagree at the balance trigger

The customer PO says 30% deposit and 70% **before shipment** (`sources/po-de-001.txt`, line 10). The confirmation wiki says the 70% balance is due **against a copy of the bill of lading**, with a planned date of 2026-12-20 (`wiki/case-nordlicht-confirmation.md`, line 46). These are materially different triggers; the wiki itself acknowledges the PO wording but simultaneously presents the bill-of-lading term as the payment arrangement. Supplier A’s quote also says 70% before shipment (`sources/supplier-a-quote.txt`, line 9; `sources/supplier-a-colorbox.txt`, line 9).

For the conflict example, retain the PO and quote wording as the source of record and show the wiki/B/L term as an unresolved proposed or conflicting term until there is a dated, attributable amendment. For a clean new scenario, make PO, supplier confirmation, PI, and payment schedule use one identical balance trigger. Do not silently substitute one trigger for the other.

The payment advice records the 30% deposit as received on 2026-11-25 (`sources/payment-advice.txt`, lines 5–8), while the wiki repeats that date. This is a simulated fixture claim, not a live payment verification. Keep it marked simulated and separate it from the conflicting balance-term question.

### 3. The fixture blends timelines and specification versions

The Nordlicht confirmation wiki is dated 2026-04-12 and cites a 2026-04-18 packaging change (`wiki/case-nordlicht-confirmation.md`, lines 3–6, 28), while its linked PO is dated 2026-11-20 (`sources/po-de-001.txt`, line 4), its deposit advice is dated 2026-11-25, and the root source `de-inquiry.eml` has no sent date. The seed registers this confirmation as case knowledge for the same Nordlicht inquiry (`demo/seed.py`, lines 168–190 and 228–231). That produces an unclear chronology in one case.

There is also a lead-time conflict: the confirmation wiki and color-box quote state 31 days after sample approval/deposit (`wiki/case-nordlicht-confirmation.md`, line 48; `sources/supplier-a-colorbox.txt`, line 7), but `sources/supplier-production-confirmation.eml`, line 4 says 28 days and names specification V2. The base quote’s 28 days is for standard packaging (`sources/supplier-a-quote.txt`, line 7); the later color-box quote says 31 days. Preserve this as a source-version/condition conflict and require a replacement supplier confirmation before treating the schedule as resolved.

The existing April/November records can remain as a separate historical or conflict scenario if their dates and relationships are made explicit. A clean new walkthrough should use one dated event sequence and ensure every confirmation names the applicable spec and packaging revision.

### 4. Nordlicht fixture is not the core15 closeout state

Both sets use Michael Weber and Nordlicht-like identity markers, but the demo-v2 fixture is a distinct case (`inq_demo_de`, `demo/seed.py`, lines 168–190), whereas core15 is `BAG-2026-DE-001` (`test/core15/manifest.json`, lines 2–6). Their scopes and states conflict:

- Demo-v2 confirmation describes dark gray, recycled polyester, YKK zipper, embroidered 60 × 25 mm logo, CB-02 box 32 × 47 × 17 cm, and 20/carton (`wiki/case-nordlicht-confirmation.md`, lines 14–29).
- Core15 is a navy WB-26 with 600D polyester/PU backing, unbranded nylon #5 zipper, woven logo 60 × 18 mm, 46 × 33 × 8 cm box, and five/carton (`test/scripts/core15_content.json`, especially evidence/artifact entries around lines 275–276, 361, 417 and 1147; source email `test/core15/evidence/closeout-customer-technical-confirmation.eml`).
- Demo-v2 says the customer approves the sample for mass production (`sources/customer-sample-approval.eml`, line 6) and includes an accepted order and deposit advice. Core15 explicitly limits sample approval to S03/V3, says it is not production authorization, and keeps PI/SC unsigned, deposit receipt unevidenced, and production release blocked (`test/core15/manifest.json`, lines 22–34; `test/core15/evidence/closeout-customer-sample-approval-s03.eml`).

Do not load the demo-v2 confirmations as updates to the core15 Case or label them as core15 evidence. Keep the fixtures separate by case ID and make the demo-v2 parties explicitly fictional; the demo-v2 email domain and names otherwise resemble the core15 buyer identity while describing materially different facts.

## Recommended fixture organization

1. Preserve the 32 × 47 × 17 cm / 20-per-carton / 60 × 45 × 50 cm values as an intentional conflict example with source IDs, timestamps, and “unresolved” status. Include the B/L-copy versus before-shipment balance terms and the 28-versus-31-day schedule as separate conflict items.
2. Keep that conflict fixture isolated from the normal Nordlicht walkthrough and from `BAG-2026-DE-001`; do not publish its wiki confirmation as authoritative shared knowledge for either case.
3. Build the clear walkthrough under a new case/customer identity and consistent dates. Choose a physically feasible pack plan, then align customer spec, supplier quote/confirmation, PO, PI, and evidence to the same version. Keep sample approval, order confirmation, deposit receipt, and production release as distinct gates.
4. Label all generated approvals, signatures, bank advice, and dates as simulation data. The repository sources do not establish real customer, supplier, or payment events.

## Evidence paths reviewed

- `demo/seed.py`
- `demo/workbench_v2/wiki/case-nordlicht-confirmation.md`
- `demo/workbench_v2/sources/de-inquiry.eml`
- `demo/workbench_v2/sources/po-de-001.txt`
- `demo/workbench_v2/sources/payment-advice.txt`
- `demo/workbench_v2/sources/supplier-a-quote.txt`
- `demo/workbench_v2/sources/supplier-a-colorbox.txt`
- `demo/workbench_v2/sources/supplier-production-confirmation.eml`
- `demo/workbench_v2/sources/customer-sample-approval.eml`
- `test/core15/manifest.json`, `test/core15/evidence/*`, `test/scripts/core15_content.json`
