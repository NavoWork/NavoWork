"""Register real files in the existing demo asset library and independent Cases.

Dry run by default. --apply adds files/Cases without editing existing business
results. --event CASE_ID EVENT attaches only a named future source event.
Run using backend/.venv/Scripts/python.exe from any working directory.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / 'test/workbench_demo'


def manifest():
    data = json.loads((PACK / 'manifest.json').read_text(encoding='utf-8'))
    if data.get('schema') != 1 or data.get('simulated') is not True:
        raise ValueError('Unsupported or non-simulated manifest')
    keys = set()
    for e in data['entries']:
        path = (ROOT / e['path']).resolve()
        if not path.is_relative_to((ROOT / 'test').resolve()) or not path.is_file():
            raise ValueError(f'Invalid source path: {e["path"]}')
        if e['key'] in keys:
            raise ValueError('Duplicate asset key')
        keys.add(e['key'])
        content = path.read_bytes()
        if sha256(content).hexdigest() != e['sha256'] or len(content) != e['byteSize']:
            raise ValueError(f'File differs from manifest: {e["path"]}')
    for scenario in data['scenarios']:
        for key in scenario['initial'] + [key for event, values in scenario['events'] for key in values]:
            if key not in keys:
                raise ValueError(f'Unknown scenario source: {key}')
    return data


def prepare(database=None, storage=None):
    sys.path.insert(0, str(ROOT))
    from dev import local_env
    env = local_env()
    if env.get('APP_ENV', 'demo') != 'demo':
        raise ValueError('Only APP_ENV=demo is supported')
    if database:
        target = Path(database).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        env['DATABASE_URL'] = 'sqlite:///' + target.as_posix()
        if not storage:
            storage = target.parent / (target.stem + '-storage')
    if storage:
        env['STORAGE_ROOT'] = str(Path(storage).resolve())
    os.environ.update(env)
    os.chdir(ROOT / 'backend')
    sys.path.insert(0, str(ROOT / 'backend'))


def seed(data, *, email=None, event=None, include_regression=False, refresh_unused_sources=False):
    from sqlalchemy import select
    from app.core import WORKSPACE_ID, bootstrap, create_item, decode, store_blob, encode, items
    from app.db import Base, SessionLocal, engine
    from app.models import Blob, Case, CaseAccess, Item, Job, User, now
    from app.sop_api import _extract_file

    by_key = {e['key']: e for e in data['entries']}
    summary = dict(assetsCreated=0, assetsReused=0, casesCreated=0, evidenceCreated=0, evidenceReused=0,
                   knowledgeCreated=0, artifactsCreated=0, approvalsCreated=0, sourceVersionsCreated=0)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        bootstrap(db)
        user = db.scalar(select(User).where(User.email == (email or os.getenv('DEMO_EMAIL', 'demo@navowork.local')).lower()))
        if not user:
            raise ValueError('Target user does not exist; use an existing demo account')
        if refresh_unused_sources:
            # Development-only refresh: reject once any Case input has been consumed.
            # Assets gain immutable versions; unconsumed evidence retains its old blob/hash in history.
            for scenario in data['scenarios']:
                case = db.get(Case, scenario['id'])
                if case and (decode(case.payload).get('demoPack') != data['pack'] or case.current_revision or case.active_run_id
                             or decode(case.payload).get('pendingRunId') or db.scalar(select(Job).where(Job.case_id == case.id))
                             or any(row.kind not in ('evidence', 'message', 'canvas') for row in db.scalars(select(Item).where(Item.case_id == case.id)))):
                    raise ValueError('Sources already consumed; create a new pack or explicit business change instead')

        def add_evidence(case, key):
            e = by_key[key]
            item_id = f'ev_assetsdemo_{case.id}_{key}'
            existing = db.get(Item, item_id)
            if existing:
                v = decode(existing.payload)
                blob = db.get(Blob, v.get('blobId'))
                if not blob or not Path(blob.path).is_file() or sha256(Path(blob.path).read_bytes()).hexdigest() != v.get('sha256'):
                    raise ValueError(f'Existing evidence blob is missing or corrupt: {item_id}')
                changed_bytes = v.get('sha256') != e['sha256']
                changed_metadata = v.get('title') != e['title'] or v.get('sourceRole') != e['role']
                if (changed_bytes or changed_metadata) and refresh_unused_sources:
                    prior = dict(blobId=v['blobId'], sha256=v['sha256'], version=existing.version,
                                 title=v.get('title'), sourceRole=v.get('sourceRole'))
                    if changed_bytes:
                        replacement = store_blob(db, (ROOT / e['path']).read_bytes(), e['name'], e['mime'], case.id)
                        v.update(blobId=replacement.id, sha256=e['sha256'], text=_extract_file((ROOT / e['path']).read_bytes(), e['name']))
                    v.update(title=e['title'], sourceRole=e['role'], sourceHistory=[*v.get('sourceHistory', []), prior])
                    existing.version += 1
                    existing.payload = encode(v)
                    summary['sourceVersionsCreated'] += 1
                elif changed_bytes or changed_metadata:
                    raise ValueError(f'Existing evidence has changed; do not overwrite: {item_id}')
                summary['evidenceReused'] += 1
                return
            content = (ROOT / e['path']).read_bytes()
            blob = store_blob(db, content, e['name'], e['mime'], case.id)
            value = dict(id=item_id, caseId=case.id, title=e['title'], sourceRole=e['role'], blobId=blob.id,
                         sha256=e['sha256'], text=_extract_file(content, e['name']), parseStatus='pending',
                         status='observed', createdAt=now(), simulated=True, fixtureKey=key, fixturePack=data['pack'])
            create_item(db, 'evidence', value, case_id=case.id, item_id=item_id, status='observed')
            summary['evidenceCreated'] += 1

        if event:
            case_id, event_name = event
            scenario = next((s for s in data['scenarios'] if s['id'] == case_id), None)
            if not scenario or event_name not in dict(scenario['events']):
                raise ValueError('Unknown Case/event; see manifest scenarios')
            case = db.get(Case, case_id)
            if not case or not db.get(CaseAccess, (case_id, user.id)) or decode(case.payload).get('demoPack') != data['pack']:
                raise ValueError('Seed the Case first; only this pack and authorized account can receive events')
            for key in dict(scenario['events'])[event_name]:
                add_evidence(case, key)
        else:
            for e in data['entries']:
                if not e['defaultImport'] and not include_regression:
                    continue
                asset_id = 'asset_assetsdemo_' + e['key']
                previous = [row for row in items(db, 'asset', parent_id=asset_id)]
                version = 1
                if previous:
                    row = max(previous, key=lambda row: row.version)
                    value = decode(row.payload)
                    blob = db.get(Blob, value.get('blobId'))
                    if not blob or not Path(blob.path).is_file() or sha256(Path(blob.path).read_bytes()).hexdigest() != value.get('fixtureSha256'):
                        raise ValueError(f'Existing asset blob is missing or corrupt: {asset_id}')
                    if value.get('fixtureSha256') == e['sha256']:
                        summary['assetsReused'] += 1
                        continue
                    if not refresh_unused_sources:
                        raise ValueError(f'Existing asset changed; create an explicit new source version instead: {asset_id}')
                    version = row.version + 1
                    summary['sourceVersionsCreated'] += 1
                blob = store_blob(db, (ROOT / e['path']).read_bytes(), e['name'], e['mime'], max_mb=100)
                value = dict(id=asset_id, title=e['title'], name=e['name'], version=version, space=e['space'], ownerId=user.id,
                             folder=e['folder'], mediaType=e['mime'], size=blob.byte_size, blobId=blob.id, createdAt=now(),
                             skuScope=['BP-DE-3000-DEMO'] if e['source'] == 'workbench_demo' else [], locale='en-US',
                             source=f'SIMULATED / {e["source"]}', audience=e['audience'], fixturePack=data['pack'],
                             fixtureKey=e['key'], fixtureSha256=e['sha256'], stage=e['stage'])
                create_item(db, 'asset', value, item_id=f'{asset_id}:v{version}', parent_id=asset_id, version=version)
                summary['assetsCreated'] += 1
            db.flush()
            for scenario in data['scenarios']:
                case = db.get(Case, scenario['id'])
                if not case:
                    original = '\n\n'.join(_extract_file((ROOT / by_key[k]['path']).read_bytes(), by_key[k]['name'])
                                            for k in scenario['initial'][:1])
                    payload = dict(title=scenario['title'], customer=scenario['customer'], originalText=original,
                                   requestedLocales=['en-US'], destination='Mexico City' if 'moq' in scenario['id'] else 'London' if 'unknown' in scenario['id'] else 'Hamburg',
                                   nextAction=scenario['prompt'], demoPack=data['pack'], developmentPath=scenario['path'], simulated=True,
                                   customerContext=dict(channel='email', company=scenario['customer'],
                                                        summary='虚构演示客户；信用、公司注册与采购权限未核实。'))
                    case = Case(id=scenario['id'], workspace_id=WORKSPACE_ID, owner_id=user.id, payload=encode(payload), status='todo')
                    db.add(case)
                    db.flush()
                    db.add(CaseAccess(case_id=case.id, user_id=user.id))
                    summary['casesCreated'] += 1
                elif decode(case.payload).get('demoPack') != data['pack'] or not db.get(CaseAccess, (case.id, user.id)):
                    raise ValueError(f'Case namespace collision or no access: {case.id}')
                for key in scenario['initial']:
                    add_evidence(case, key)
            # Generic knowledge only. The legacy per-case confirmation Wiki is intentionally excluded.
            for path in sorted((ROOT / 'demo/workbench_v2/wiki').glob('[0-9][0-9]-*.md')):
                source_id = 'kb_assetsdemo_' + path.stem
                if db.get(Item, source_id + ':v1'):
                    continue
                content = path.read_text(encoding='utf-8')
                title = content.splitlines()[0].lstrip('# ')
                create_item(db, 'resource', dict(id=source_id, sourceId=source_id, title=title, folder='Demo 业务知识',
                            content=content, kind='knowledge', version=1, editVersion=1, status='published',
                            ownerId=user.id, updatedAt=now(), fixturePack=data['pack']),
                            item_id=source_id + ':v1', parent_id=source_id, status='published')
                summary['knowledgeCreated'] += 1
        db.commit()
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--database', help='Optional SQLite path; defaults to the existing app configuration')
    parser.add_argument('--storage', help='Optional blob storage path')
    parser.add_argument('--email', help='Existing demo account; defaults to DEMO_EMAIL')
    parser.add_argument('--include-regression', action='store_true', help='Also register old negative/adversarial inputs')
    parser.add_argument('--refresh-unused-sources', action='store_true', help='Authoring only: add asset versions and refresh unconsumed pack evidence; fails after any business use')
    parser.add_argument('--event', nargs=2, metavar=('CASE_ID', 'EVENT'))
    args = parser.parse_args()
    data = manifest()
    if not args.apply:
        print(json.dumps(dict(dryRun=True, defaultAssets=sum(e['defaultImport'] for e in data['entries']),
                              cases=[dict(id=s['id'], initial=len(s['initial']), events=[n for n, _ in s['events']]) for s in data['scenarios']],
                              creates='assets, evidence, Cases, generic knowledge only; no business results or approvals'), ensure_ascii=False, indent=2))
        return
    prepare(args.database, args.storage)
    print(json.dumps(seed(data, email=args.email, event=args.event, include_regression=args.include_regression,
                          refresh_unused_sources=args.refresh_unused_sources), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
