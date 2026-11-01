"""Recover ONLY proven newline-converted source bytes; never reseal changed facts.

--apply writes a candidate only when it matches the original recorded SHA-256
and differs from the working file solely by CRLF/LF conversion. Read-only by default.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def repair(apply=False):
    expected = {}
    for path in (ROOT / 'test/cases').glob('*.json'):
        for source in json.loads(path.read_text(encoding='utf-8-sig'))['sources']:
            expected[source['storage_uri']] = source['sha256']
    core = json.loads((ROOT / 'test/core15/manifest.json').read_text(encoding='utf-8-sig'))
    # Historical evidence copies must remain byte-identical to their original mail.
    copies = {
        'original-inquiry.eml': 'inquiry.eml',
        'original-change-color-box.eml': 'change-color-box.eml',
        'original-customer-conditional-confirmation.eml': 'customer-conditional-confirmation.eml',
    }
    for evidence in core['evidence']:
        if Path(evidence['path']).name in copies:
            expected['test/core15/' + evidence['path']] = evidence['sha256']
    fixes = []
    for relative, digest in expected.items():
        path = ROOT / relative
        content = path.read_bytes()
        if sha256(content).hexdigest() == digest:
            continue
        if path.name in copies and relative.startswith('test/core15/'):
            candidate = (ROOT / 'test/inputs/BAG-2026-DE-001' / copies[path.name]).read_bytes()
            origin = 'byte-exact original source mail'
        else:
            candidate = subprocess.check_output(['git', 'show', 'HEAD:' + relative], cwd=ROOT)
            origin = 'HEAD Git blob'
        if sha256(candidate).hexdigest() != digest or content.replace(b'\r\n', b'\n') != candidate.replace(b'\r\n', b'\n'):
            raise ValueError(f'Refusing unproven repair: {relative}')
        if apply:
            path.write_bytes(candidate)
        fixes.append(dict(path=relative, expectedSha256=digest, source=origin, applied=apply))
    return fixes


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(repair(args.apply), ensure_ascii=False, indent=2))
