"""Validate the mock documents themselves; this does not exercise an application."""
from pathlib import Path
from hashlib import sha256
from decimal import Decimal, ROUND_UP
from email import policy
from email.parser import BytesParser
import json
import sys
import re
from pypdf import PdfReader
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'core15'
QA = ROOT / '.qa' / 'core15'
content = json.loads((ROOT / 'scripts' / 'core15_content.json').read_text(encoding='utf-8-sig'))
manifest = json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))
errors = []


def check(condition, text):
    if not condition:
        errors.append(text)


def clean(text):
    return re.sub(r'\s+', '', str(text))


check([c['id'] for c in manifest['categories']] == list(range(1, 16)), '15 categories must be present and ordered')
check(manifest['simulation_only'] is True, 'snapshot must be simulated')
check(manifest['case_id'] == 'BAG-2026-DE-001', 'wrong case')
check(manifest['snapshot'] == 'core15_closeout_2026-10-31', 'wrong follow-up snapshot')
check(manifest['gates']['production_release'] == 'blocked', 'production release must remain blocked')
check(manifest['commercial']['deposit_received'] is None, 'deposit receipt is unknown, not received')
check('PI/SC not signed' in manifest['gates']['production_blockers'], 'unsigned documents must remain a blocker')

listed = [f for c in manifest['categories'] for f in c['files']]
check(len(listed) == len(set(listed)) == 17, 'expect 17 unique business files for 15 categories')
check(sum(f.endswith('.pdf') for f in listed) == 15, 'expect 15 PDFs')
check(sum(f.endswith('.xlsx') for f in listed) == 2, 'expect 2 XLSX files')
document_text = {}
for c in content['categories']:
    for item in c.get('documents', [c]):
        if c['id'] in (8, 9):
            continue
        p = OUT / item['filename']
        check(p.is_file(), f'missing PDF {p.name}')
        if not p.is_file():
            continue
        reader = PdfReader(p)
        text = ''.join(page.extract_text() or '' for page in reader.pages)
        document_text[p.name] = text
        normalized = clean(text)
        check(len(reader.pages) >= 1, f'empty PDF: {p.name}')
        check('SIMULATED' in text, f'simulation label missing: {p.name}')
        check(clean(item.get('title_zh', c['title_zh'])) in normalized, f'title missing: {p.name}')
        for section in item['sections']:
            for label, value in section['rows']:
                check(clean(label) in normalized, f'PDF label missing: {p.name}: {label}')
                check(clean(value) in normalized, f'PDF value missing: {p.name}: {label}')
check('Customer Request for Quotation' in document_text.get('02_customer_RFQ.pdf', ''), 'customer RFQ must not be replaced by supplier RFQ')

original = json.loads((ROOT / 'cases' / 'BAG-2026-DE-001.json').read_text(encoding='utf-8-sig'))
known_ids = {s['id'] for s in original['sources']} | {e['id'] for e in content['evidence']}
by_evidence = {e['id']: e for e in content['evidence']}
new_mails = 0
for e in manifest['evidence']:
    p = (OUT / e['path']).resolve()
    check(p.is_relative_to(ROOT.resolve()), f'evidence path escapes test: {e["path"]}')
    check(p.is_file(), f'missing evidence {e["path"]}')
    if not p.is_file():
        continue
    check(sha256(p.read_bytes()).hexdigest() == e['sha256'], f'evidence digest mismatch {p.name}')
    if e.get('existing_source'):
        continue
    new_mails += 1
    source = by_evidence[e['id']]
    msg = BytesParser(policy=policy.default).parsebytes(p.read_bytes())
    check(msg['Message-ID'] == source['message_id'], f'email Message-ID mismatch {p.name}')
    check(msg['X-Demo-Data'] == 'SIMULATED', f'email simulation header missing {p.name}')
    body = msg.get_body(preferencelist=('plain',)).get_content()
    check(source['body'].replace('\r\n', '\n') in body.replace('\r\n', '\n'), f'email body differs from content {p.name}')
check(new_mails == 6, 'expect six new evidence emails')
for c in content['categories']:
    for item in c.get('documents', [c]):
        for evidence_id in item.get('evidence_ids', []):
            check(evidence_id in known_ids, f'unknown evidence reference {evidence_id}')

quantity = Decimal('3000')
cost = sum(Decimal(x) for x in ('44', '5', '4'))
unit = (cost / Decimal('7.20') / (1 - Decimal('0.20'))).quantize(Decimal('0.01'), rounding=ROUND_UP)
check(unit == Decimal('9.21') and unit * quantity == Decimal('27630'), 'independent pricing failed')
check(Decimal('8289') + Decimal('19341') == unit * quantity, 'payment split does not reconcile')
for p in ('10_customer_quotation_V3.pdf', '14a_PO_DE-PO-2026-118-R2.pdf', '14b_PI-26031-003.pdf', '14c_SC-26031-003.pdf', '15_order_technical_annex_V3.pdf'):
    t = document_text.get(p, '')
    check('27,630.00' in t and '9.21' in t, f'commercial numbers inconsistent: {p}')
    check('FOB Ningbo' in t or p.startswith('15_'), f'trade term missing: {p}')
    check('V3' in t and 'S03' in t, f'technical/sample version missing: {p}')

for category_id, sheet_name, expected_values in [
    (8, 'Supplier Quote V3', {'B11': 3000, 'B12': 44, 'B13': 5, 'B14': 49, 'B16': 3000, 'B17': 28}),
    (9, 'Costing V3', {'B6': 9.21, 'B7': 27630, 'B8': 8289, 'B9': 19341, 'B15': 44, 'B16': 5, 'B17': 4, 'B18': 53, 'B22': 3000, 'B23': 7.2, 'B24': 0.2, 'B25': 0.3}),
]:
    filename = next(c['files'][0] for c in manifest['categories'] if c['id'] == category_id)
    p = OUT / filename
    check(p.suffix == '.xlsx' and p.is_file(), f'missing XLSX {filename}')
    if not p.is_file():
        continue
    wb = load_workbook(p, data_only=True, read_only=True)
    sheet = wb[sheet_name]
    for address, value in expected_values.items():
        actual = sheet[address].value
        check(isinstance(actual, (int, float)) and abs(actual - value) < 1e-8, f'XLSX value mismatch {filename}:{address}')
    wb.close()
    wf = load_workbook(p, data_only=False, read_only=True)
    formula_cell = 'B14' if category_id == 8 else 'B6'
    check(str(wf[sheet_name][formula_cell].value).startswith('='), f'formula missing {filename}:{formula_cell}')
    wf.close()
live_checks = json.loads((QA / 'costing-live-checks.json').read_text(encoding='utf-8'))
check(len(live_checks) == 4, 'four actual recalculation checks must be recorded')
check(all(c['actual'] == c['expected'] for c in live_checks), 'live input/rounding/missing-input checks failed')

# Explicit sealing happens only after generation, never as part of a normal read-only check.
current_hashes = {name: sha256((OUT / name).read_bytes()).hexdigest() for name in listed if (OUT / name).is_file()}
if '--seal' in sys.argv and not errors:
    manifest['artifact_hashes'] = current_hashes
    manifest['approval_bindings'] = [
        {'scope': 'sample_S03_and_TechPack_V3', 'evidence_id': 'ev-closeout-customer-sample-1030', 'target_file': '13_final_sample_confirmation.pdf', 'sha256': current_hashes['13_final_sample_confirmation.pdf']},
        {'scope': 'Quotation_V3_price_only', 'evidence_id': 'ev-closeout-manager-approval-1130', 'target_file': '10_customer_quotation_V3.pdf', 'sha256': current_hashes['10_customer_quotation_V3.pdf']},
    ]
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
check(manifest.get('artifact_hashes') == current_hashes, 'business file hash seal missing or stale; use --seal after rebuilding')
for binding in manifest.get('approval_bindings', []):
    check(current_hashes.get(binding['target_file']) == binding['sha256'], 'version-bound approval snapshot hash changed')
if errors:
    print('FAIL: core15 fixture consistency')
    for e in errors:
        print(' -', e)
    sys.exit(1)
print('PASS: 15 categories, 17 native business files, 6 new email sources; all PDF table content, XLSX formulas/caches/live checks, money, version links, hashes and pending gates verified.')
