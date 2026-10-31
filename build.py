#!/usr/bin/env python3
"""Build an offline, standalone demo with the Python standard library."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
html = (ROOT / 'index.html').read_text(encoding='utf-8')
css = (ROOT / 'styles.css').read_text(encoding='utf-8')
html = re.sub(r'<link rel="stylesheet" href="styles\.css(?:\?[^"]*)?">', lambda _: '<style>\n' + css + '\n</style>', html)
for filename in ('domain.js', 'cases.js', 'app.js'):
    source = (ROOT / filename).read_text(encoding='utf-8').replace('</script', '<\\/script')
    html = re.sub(r'<script src="'+re.escape(filename)+r'(?:\?[^"]*)?"></script>', lambda _: '<script>\n' + source + '\n</script>', html)
output = ROOT / 'dist' / 'demo.html'
output.parent.mkdir(exist_ok=True)
output.write_text(html, encoding='utf-8')
print(f'Built {output} ({output.stat().st_size:,} bytes)')
