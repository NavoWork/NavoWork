"""Validate source bytes and optionally exercise real authenticated backend APIs.

--api uses disposable SQLite/storage and never the developer's active database.
Reports distinguish fixture checks, actual API checks and untested model services.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, ROUND_CEILING
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import tempfile
import zipfile

from seed_workbench_demo import ROOT, PACK, manifest, prepare, seed

QA = ROOT / 'test/.qa/workbench_demo'


def static_checks(data):
    from pypdf import PdfReader
    from openpyxl import load_workbook
    from PIL import Image
    from email import policy
    from email.parser import BytesParser
    categories = {e['category'] for e in data['entries'] if e['source'] == 'workbench_demo'}
    assert set(range(1, 16)) <= categories
    for e in data['entries']:
        path = ROOT / e['path']
        if path.suffix == '.pdf':
            reader = PdfReader(path)
            text = '\n'.join(p.extract_text() or '' for p in reader.pages)
            assert 'SIMULATED' in text, e['key']
            if e['audience'] == 'customer' and e['source'] == 'workbench_demo':
                assert not any(term in text.lower() for term in ['target gross margin', 'manufacturing cny', 'unit cost cny']), e['key']
        elif path.suffix == '.xlsx':
            wb = load_workbook(path, data_only=True, read_only=True)
            assert len(wb.sheetnames) > 0
            wb.close()
        elif path.suffix in ('.png', '.jpg'):
            with Image.open(path) as image:
                image.verify()
        elif path.suffix == '.eml' and e['source'] == 'workbench_demo':
            mail = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
            assert '.invalid' in mail['From'] and mail['Message-ID'] and 'SIMULATED' in mail['Subject']
            assert mail.get_body(preferencelist=('plain',)).get_content().strip()
    for key, total in [('bom_V1', 50), ('bom_V2', 53)]:
        wb = load_workbook(PACK / 'assets' / (key + '.xlsx'), data_only=True, read_only=True)
        assert wb['BOM']['J13'].value == total
        rows = list(wb['BOM'].iter_rows(min_row=2, max_row=12, values_only=True))
        independent = sum(Decimal(str(r[3])) * Decimal(str(r[6])) * (1 + Decimal(str(r[7]))) for r in rows)
        assert independent == Decimal(total)
        wb.close()
    wb = load_workbook(PACK / 'assets/09_costing_editable.xlsx', data_only=True, read_only=True)
    assert wb['Costing']['B2'].value == 8.69 and wb['Costing']['B3'].value == 26070
    wb.close()
    assert (Decimal(53) / Decimal('7.2') / Decimal('.8')).quantize(Decimal('.01'), rounding=ROUND_CEILING) == Decimal('9.21')
    assert 2 * 47 * 32 * 17 < 50 * 35 * 38
    assert 20 * 32 * 47 * 17 > 60 * 45 * 50
    recalc = json.loads((QA / 'sheet-recalculation.json').read_text(encoding='utf-8'))
    assert all(c['expected'] == c['actual'] for c in recalc)
    return dict(assetHashes=len(data['entries']), coreCategories=15, scenarios=len(data['scenarios']),
                formats=dict(Counter(Path(e['path']).suffix for e in data['entries'])),
                defaultAssets=sum(e['defaultImport'] for e in data['entries']),
                artifactEngineRecalculationCases=len(recalc), result='passed')


def inventory():
    result = []
    for base in [ROOT / 'backend/data', ROOT / 'data']:
        if not base.exists():
            continue
        for path in sorted(base.rglob('*')):
            if path.suffix not in ('.sqlite', '.sqlite3', '.db') or not path.is_file():
                continue
            item = dict(path=path.relative_to(ROOT).as_posix(), tables={}, missingBlobs=0, corruptBlobs=0)
            try:
                with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
                    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    for table in ['cases', 'items', 'blobs', 'jobs', 'runs']:
                        if table in names:
                            item['tables'][table] = db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                    if 'items' in names:
                        item['itemKinds'] = dict(db.execute('SELECT kind, COUNT(*) FROM items GROUP BY kind'))
                    if 'blobs' in names:
                        for name, size, digest in db.execute('SELECT path, byte_size, sha256 FROM blobs'):
                            target = Path(name)
                            if not target.is_absolute():
                                target = ROOT / 'backend' / target
                            if not target.is_file():
                                item['missingBlobs'] += 1
                            elif target.stat().st_size != size or sha256(target.read_bytes()).hexdigest() != digest:
                                item['corruptBlobs'] += 1
            except sqlite3.DatabaseError as e:
                item['error'] = str(e)
            result.append(item)
    return result


def api_checks(data):
    # Freeze temporary paths BEFORE importing app.db or app.core.
    with tempfile.TemporaryDirectory(prefix='navowork-assets-api-', ignore_cleanup_errors=True) as tmp:
        prepare(Path(tmp) / 'demo.sqlite3', Path(tmp) / 'storage')
        import os
        os.environ['MODEL_API_KEY'] = ''
        from fastapi.testclient import TestClient
        from app.main import app
        from app.db import SessionLocal, engine
        from app.core import items, decode, password_hash
        from app.models import User
        from workbench_demo_content import SPEC

        first = seed(data)
        with SessionLocal() as db:
            before = {row.id: row.payload for row in items(db, 'evidence') + items(db, 'asset')}
        second = seed(data)
        assert second['assetsCreated'] == second['casesCreated'] == second['evidenceCreated'] == 0
        with SessionLocal() as db:
            assert before == {row.id: row.payload for row in items(db, 'evidence') + items(db, 'asset')}

        observations = dict(seed=first, repeatSeed=second, downloads=0, initialCases=0, office=[], costs=[],
                            researchSources=0, exports=[], modelCallsExecuted=False,
                            limitations=['Live language-model runs, external image generation and VLM recognition were not executed.',
                                         'Guarded IF/AND/COUNT workbooks are valid Excel sources but unsupported by the current basic app formula editor.'])
        with TestClient(app) as client:
            login = client.post('/api/v1/auth/session', json=dict(email=os.getenv('DEMO_EMAIL', 'demo@navowork.local'), password=os.getenv('DEMO_PASSWORD', 'ChangeMe123!')))
            assert login.status_code == 200, login.text
            base = '/api/v1/workspaces/ws_demo'
            response = client.get(base + '/library/assets')
            assert response.status_code == 200
            assets = {a['id']: a for a in response.json()['items']}
            for e in data['entries']:
                if not e['defaultImport']:
                    continue
                asset = assets['asset_assetsdemo_' + e['key']]
                download = client.get('/api/v1' + asset['downloadPath'])
                assert download.status_code == 200 and sha256(download.content).hexdigest() == e['sha256'], e['key']
                observations['downloads'] += 1
            for scenario in data['scenarios']:
                path = base + '/inquiries/' + scenario['id']
                r = client.get(path + '/workbench')
                assert r.status_code == 200, r.text
                state = r.json()
                assert state['artifacts'] == {} and state['approvals'] == [] and state['case']['currentRevision'] == 0
                assert state['gate']['status'] == 'blocked'
                assert len(state['evidence']) == len(scenario['initial'])
                for evidence in state['evidence']:
                    if evidence['id'].endswith('_09_costing_editable'):
                        assert evidence['sourceRole'] == 'internal_note'
                assert not any(e['id'].endswith('customer-sample-v2') for e in state['evidence'])
                observations['initialCases'] += 1

            case_path = base + '/inquiries/inq_assets_odm'
            # Real upload endpoint, extraction and hash-preserving download for each main format.
            for key, ext in [('02_customer_RFQ', 'pdf'), ('bom_V1', 'xlsx'), ('product-reference', 'png')]:
                file = PACK / 'assets' / f'{key}.{ext}'
                r = client.post(case_path + '/evidence', files={'file': (file.name, file.read_bytes())}, data={'sourceRole': 'internal_note'})
                assert r.status_code == 200, r.text
                uploaded = r.json()
                if ext in ('pdf', 'xlsx'):
                    assert uploaded['text'].strip()
                assert sha256(client.get(case_path + '/evidence/' + uploaded['id'] + '/download').content).hexdigest() == sha256(file.read_bytes()).hexdigest()
            # Exercise every new workbook and both original core15 workbooks against the actual editor.
            book_entries = [e for e in data['entries'] if e['defaultImport'] and Path(e['path']).suffix == '.xlsx']
            for e in book_entries:
                source = client.post(case_path + '/evidence', files={'file': (e['name'], (ROOT/e['path']).read_bytes(), e['mime'])}, data={'sourceRole': 'supplier_quote'}).json()
                opened = client.post(case_path + '/workbench/office', json={'fileId': source['id']})
                guarded = e['key'] in ('09_costing', 'bom_missing_price', 'legacy_09_costing')
                expected = 422 if guarded else 200
                assert opened.status_code == expected, (e['key'], opened.status_code, opened.text[:500])
                observations['office'].append(dict(key=e['key'], status=opened.status_code, supported=not guarded))
                if e['key'] == '09_costing_editable':
                    v = opened.json()
                    modified = client.put(case_path + '/workbench/office/' + v['documentId'], json=dict(baseVersion=1, baseHash=v['sha256'], operations=[dict(op='set_cell', sheet='Costing', cell='B8', value=5)]))
                    assert modified.status_code == 200, modified.text
                    from openpyxl import load_workbook
                    wb = load_workbook(BytesIO(client.get(modified.json()['downloadUrl']).content), data_only=True)
                    assert wb['Costing']['B2'].value == 9.21 and wb['Costing']['B3'].value == 27630
                    wb.close()
                    assert client.put(case_path + '/workbench/office/' + v['documentId'], json=dict(baseVersion=1, baseHash=v['sha256'], operations=[dict(op='set_cell', sheet='Costing', cell='B8', value=2)])).status_code == 409
            from app.domain import SPEC_KEYS
            assert set(SPEC) <= set(SPEC_KEYS)
            spec = client.put(case_path + '/workbench/artifacts/spec', json=dict(baseVersion=0, content=dict(fields=SPEC)))
            assert spec.status_code == 200, spec.text
            try:
                seed(data, refresh_unused_sources=True)
            except ValueError as exc:
                assert 'Sources already consumed' in str(exc)
                observations['consumedSourcesRefreshRejected'] = True
            else:
                raise AssertionError('Source refresh must reject consumed Cases')
            initial_source = 'ev_assetsdemo_inq_assets_odm_supplier_A_V1'
            def cost_body(pack, source, version):
                return dict(baseVersion=version, content=dict(lines=[
                    dict(category='labor', label='Manufacturing including materials', amountCny='44', sourceId=source),
                    dict(category='packaging', label='Packaging', amountCny=str(pack), sourceId=source),
                    dict(category='domesticFreight', label='Local handling only', amountCny='4', sourceId=source)],
                    exchangeRate='7.20', margin='0.20', quantity=3000))
            r = client.put(case_path + '/workbench/artifacts/cost', json=cost_body(2, initial_source, 0))
            assert r.status_code == 200, r.text
            assert r.json()['content']['unitPriceUsd'] == '8.69'
            observations['costs'].append(dict(version=1, unitPriceUsd=r.json()['content']['unitPriceUsd'], totalUsd=r.json()['content']['totalUsd']))
            event_result = seed(data, event=['inq_assets_odm', 'colorbox'])
            assert event_result['evidenceCreated'] == 5
            again = seed(data, event=['inq_assets_odm', 'colorbox'])
            assert again['evidenceCreated'] == 0
            r = client.put(case_path + '/workbench/artifacts/cost', json=cost_body(5, 'ev_assetsdemo_inq_assets_odm_supplier_A_V2', 1))
            assert r.status_code == 200, r.text
            assert r.json()['content']['unitPriceUsd'] == '9.21' and r.json()['content']['totalUsd'] == '27630.00'
            observations['costs'].append(dict(version=2, unitPriceUsd=r.json()['content']['unitPriceUsd'], totalUsd=r.json()['content']['totalUsd']))
            for fmt, signature in [('pdf', b'%PDF'), ('xlsx', b'PK'), ('docx', b'PK')]:
                exported = client.post(case_path + '/workbench/artifacts/cost/export', json={'format': fmt})
                assert exported.status_code == 200, exported.text
                downloaded = client.get(exported.json()['downloadUrl'])
                assert downloaded.status_code == 200 and downloaded.content.startswith(signature)
                if fmt in ('docx', 'xlsx'):
                    with zipfile.ZipFile(BytesIO(downloaded.content)) as archive:
                        assert ('word/document.xml' if fmt == 'docx' else 'xl/workbook.xml') in archive.namelist()
                observations['exports'].append(dict(format=fmt, byteSize=len(downloaded.content), sha256=sha256(downloaded.content).hexdigest()))
            design = base + '/inquiries/inq_assets_design'
            for key in ['competitor_a', 'competitor_b']:
                located = client.get(design + '/workbench/research/sources/ev_assetsdemo_inq_assets_design_' + key)
                assert located.status_code == 200 and located.json()['sections'], located.text
                observations['researchSources'] += 1
            # Material events alone must never create approvals or manufacture release.
            seed(data, event=['inq_assets_odm', 'sample_approval'])
            state = client.get(case_path + '/workbench').json()
            assert state['approvals'] == []
            assert state['gate']['status'] == 'blocked'
            assert not any(key == 'production' for key in state['artifacts'])
            isolated = client.get(base + '/inquiries/inq_assets_unknown/evidence/' + initial_source)
            assert isolated.status_code == 404
            with SessionLocal() as db:
                db.add(User(id='asset-audit-other', email='other@example.invalid', name='Other', role='member', password_hash=password_hash('LocalDemo123!')))
                db.commit()
            with TestClient(app) as other:
                assert other.post('/api/v1/auth/session', json=dict(email='other@example.invalid', password='LocalDemo123!')).status_code == 200
                private = assets['asset_assetsdemo_personal-demo-notes']
                assert other.get('/api/v1' + private['downloadPath']).status_code == 404
                assert other.get(case_path + '/workbench').status_code == 404
        engine.dispose()
        observations['result'] = 'passed'
        return observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api', action='store_true')
    args = parser.parse_args()
    QA.mkdir(parents=True, exist_ok=True)
    data = manifest()
    report = dict(fixture=static_checks(data), localDatabases=inventory())
    if args.api:
        report['backendApi'] = api_checks(data)
    (QA / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
