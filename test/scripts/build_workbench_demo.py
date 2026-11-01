"""Generate real source documents and a portable asset/evidence manifest.

Run with bundled Python, then build_workbench_demo_sheets.mjs, then --finalize.
No application database, existing source or approved artifact is modified.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from email import policy
from email.message import EmailMessage
from hashlib import sha256
from html import escape
import json
import mimetypes
from pathlib import Path
from functools import partial
import zipfile

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer

from workbench_demo_content import DATE, DOCUMENTS, EMAILS, SCENARIOS, COLUMNS, bom_rows

REPO = Path(__file__).resolve().parents[2]
PACK = REPO / 'test/workbench_demo'
OUT = PACK / 'assets'
QA = REPO / 'test/.qa/workbench_demo'


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def generate():
    OUT.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont('DemoBody', 'C:/Windows/Fonts/msyh.ttc', subfontIndex=0))
    pdfmetrics.registerFont(TTFont('DemoBold', 'C:/Windows/Fonts/msyhbd.ttc', subfontIndex=0))
    styles = {
        'title': ParagraphStyle('title', fontName='DemoBold', fontSize=19, leading=27, textColor=colors.HexColor('#17324D'), spaceAfter=12, wordWrap='CJK'),
        'section': ParagraphStyle('section', fontName='DemoBold', fontSize=11, leading=16, spaceBefore=12, spaceAfter=6, keepWithNext=True, wordWrap='CJK'),
        'body': ParagraphStyle('body', fontName='DemoBody', fontSize=9, leading=14, wordWrap='CJK'),
        'small': ParagraphStyle('small', fontName='DemoBody', fontSize=8, leading=12, textColor=colors.HexColor('#526879'), wordWrap='CJK'),
    }

    def p(text, style='body'):
        return Paragraph(escape(str(text)), styles[style])

    def footer(c, d):
        c.saveState()
        c.setFont('DemoBody', 7)
        c.drawString(40, 22, f'SIMULATED / 虚构演示资料   {DATE}   NavoWork asset demo')
        c.drawRightString(A4[0] - 40, 22, str(d.page))
        c.restoreState()

    for item in DOCUMENTS:
        document = SimpleDocTemplate(str(OUT / (item['key'] + '.pdf')), pagesize=A4,
                                     leftMargin=40, rightMargin=40, topMargin=35, bottomMargin=38,
                                     title=item['title'], author='NavoWork Demo', invariant=1)
        story = [p('SIMULATED - all companies, prices, confirmations and observations are fictional', 'small'),
                 Spacer(1, 8), p(item['title'], 'title'),
                 p(f'Date: {DATE}   Source: {item["key"]}   Audience: {item["audience"]}', 'small')]
        for title, rows in item['sections']:
            story.append(p(title, 'section'))
            table = Table([[p(k), p(v)] for k, v in rows], colWidths=[133, A4[0] - 213])
            table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#EDF2F7')),
                ('LINEBELOW', (0, 0), (-1, -1), .3, colors.HexColor('#D9E3EB')),
                ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 4 if item['key'] == '05_techpack_V2' else 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 4 if item['key'] == '05_techpack_V2' else 5),
            ]))
            story.append(table)
        document.build(story, onFirstPage=footer, onLaterPages=footer, canvasmaker=partial(Canvas, invariant=1))

    for key, role, sender, subject, body in EMAILS:
        msg = EmailMessage(policy=policy.SMTP)
        msg['From'], msg['To'] = sender, 'sales@navowork.example.invalid'
        msg['Date'] = 'Sun, 01 Nov 2026 09:00:00 +0800'
        msg['Message-ID'] = f'<{key}-20261101@demo.example.invalid>'
        msg['Subject'] = 'SIMULATED ' + subject
        msg.set_content('SIMULATED / fictional business source\n\n' + body + '\n', charset='utf-8')
        (OUT / (key + '.eml')).write_bytes(msg.as_bytes())

    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 24)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 19)
    image = Image.new('RGB', (1000, 950), '#F4F7FA')
    draw = ImageDraw.Draw(image)
    draw.text((42, 28), 'SIMULATED PRODUCT REFERENCE', font=font, fill='#17324D')
    draw.text((42, 68), 'Illustration only. No engineering measurements or AI generation claimed.', font=small, fill='#526879')
    draw.rounded_rectangle((280, 170, 720, 810), radius=85, fill='#3B424B', outline='#1F2937', width=5)
    draw.rounded_rectangle((380, 125, 620, 250), radius=40, outline='#1F2937', width=22)
    draw.rounded_rectangle((340, 570, 660, 760), radius=30, fill='#505862', outline='#1F2937', width=4)
    draw.line((350, 600, 650, 600), fill='#E69D35', width=9)
    draw.rounded_rectangle((420, 370, 580, 425), radius=5, fill='#E8EDF3')
    draw.text((452, 383), 'DEMO', font=small, fill='#17324D')
    draw.text((42, 875), 'No dimensions, certification or physical sample approval inferred from image.', font=small, fill='#526879')
    image.save(OUT / 'product-reference.png')
    logo = Image.new('RGB', (600, 250), '#EDF2F7')
    logo_draw = ImageDraw.Draw(logo)
    logo_draw.text((180, 70), 'DEMO', font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 65), fill='#17324D')
    logo_draw.text((160, 190), 'SIMULATED ARTWORK', font=small, fill='#526879')
    logo.save(OUT / 'logo-demo-png.png')
    image = Image.new('RGB', (1250, 700), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((35, 25), 'SIMULATED SUPPLIER BOM - DELIBERATE TOTAL CONFLICT', font=font, fill='#17324D')
    draw.text((35, 68), 'NL-ALLOC-V1. Values per bag in CNY. Source total must be checked.', font=small, fill='#526879')
    y = 115
    for row in bom_rows(1):
        amount = round(row[3] * row[6] * (1 + row[7]), 4)
        draw.text((40, y), row[1], font=small, fill='#263A49')
        draw.text((470, y), f'{row[3]} x {row[6]} x (1 + {row[7]})', font=small, fill='#263A49')
        draw.text((1030, y), f'{amount:.2f}', font=small, fill='#263A49')
        y += 38
    draw.text((40, y + 14), 'Supplier printed TOTAL: CNY 49.00', font=font, fill='#991B1B')
    draw.text((40, y + 57), 'NEGATIVE FIXTURE: actual row sum is CNY 50.00; do not silently overwrite source.', font=small, fill='#991B1B')
    image.save(OUT / 'bom_image_conflict.png')
    (OUT / 'logo-demo.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="250" viewBox="0 0 600 250"><rect width="600" height="250" fill="#edf2f7"/><text x="300" y="145" text-anchor="middle" font-family="Arial" font-size="78" fill="#17324d">DEMO</text><text x="300" y="220" text-anchor="middle" font-family="Arial" font-size="24">SIMULATED ARTWORK</text></svg>', encoding='utf-8')
    (OUT / 'supplier_M_MOQ.txt').write_text('SIMULATED supplier M offer, 2026-11-01\nCotton tote 38 x 42 cm, natural, single-color logo. MOQ 500 pcs. Customer requested 300 pcs, not accepted by supplier. Unit price UNKNOWN; sample fee UNKNOWN; production time UNKNOWN. No quotation for 300 pcs.\n', encoding='utf-8')
    (OUT / 'personal-demo-notes.md').write_text('# SIMULATED personal notes\n\nAsk the buyer to clarify the deadline and budget. These private notes are not shared Case evidence or customer confirmation.\n', encoding='utf-8')
    sheets = [dict(key=f'bom_V{v}', type='bom', rows=bom_rows(v), title=f'NL BOM V{v}') for v in (1, 2)]
    sheets.append(dict(key='bom_missing_price', type='bom', rows=bom_rows(1, missing=True), title='BOM missing logo price'))
    sheets += [dict(key=key, type='supplier', title=title, values=values) for key, title, values in [
        ('supplier_A_V1', 'Factory A standard quote', [44, 2, 4, 1000, 28]),
        ('supplier_A_V2', 'Factory A color box quote', [44, 5, 4, 1000, 31]),
        ('supplier_B_V1', 'Factory B standard quote', [46, 2, 4, 1000, 23]),
    ]]
    sheets.append(dict(key='09_costing', type='costing', title='NL conditional costing'))
    sheets.append(dict(key='09_costing_editable', type='costing_simple', title='NL basic editable costing'))
    write_json(PACK / 'sheet_content.json', dict(columns=COLUMNS, sheets=sheets))


def finalize():
    entries = []

    def add(key, path, title, role='internal_note', folder='参考资料', category=0, audience='internal',
            stage='reference', space='company', source='workbench_demo', default=True):
        data = path.read_bytes()
        entries.append(dict(key=key, path=path.relative_to(REPO).as_posix(), name=path.name, title=title,
                            mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream',
                            sha256=sha256(data).hexdigest(), byteSize=len(data), role=role, folder=folder,
                            category=category, audience=audience, stage=stage, space=space, source=source,
                            defaultImport=default))

    for d in DOCUMENTS:
        add(d['key'], OUT / (d['key'] + '.pdf'), d['title'], d['role'], d['folder'], d['category'], d['audience'], d['stage'])
    for key, role, sender, title, body in EMAILS:
        add(key, OUT / (key + '.eml'), title, role, 'Nordlicht/分阶段追加原件', stage='followup')
    sheets = json.loads((PACK / 'sheet_content.json').read_text(encoding='utf-8'))['sheets']
    for s in sheets:
        category = 9 if s['type'].startswith('costing') else 8 if s['type'] == 'supplier' else 0
        add(s['key'], OUT / (s['key'] + '.xlsx'), s['title'], 'internal_note' if s['type'].startswith('costing') else 'supplier_quote',
            'Nordlicht/BOM与核价', category, stage='initial' if s['key'] in ('bom_V1', 'supplier_A_V1', 'supplier_B_V1') else 'reference')
    for key, ext, title in [('product-reference', 'png', '产品结构示意（非实物）'), ('logo-demo', 'svg', '演示 LOGO'), ('logo-demo-png', 'png', '演示 LOGO PNG'),
                            ('bom_image_clear', 'png', '清晰 BOM 表格图'), ('bom_image_missing', 'png', 'BOM 缺价表格图'),
                            ('bom_image_conflict', 'png', 'BOM 合计冲突图'), ('supplier_M_MOQ', 'txt', 'MOQ 500，300件未报价')]:
        add(key, OUT / f'{key}.{ext}', title, 'supplier_quote' if key.startswith(('bom_', 'supplier_')) else 'internal_note',
            'BOM识别/异常输入' if 'image_' in key else '产品素材')
    add('personal-demo-notes', OUT / 'personal-demo-notes.md', '个人澄清问题笔记', folder='个人工作/演示笔记', space='personal')
    # Register the original 15-category documents as historical assets, never as new Case facts.
    for path in sorted((REPO / 'test/core15').glob('*')):
        if path.suffix in ('.pdf', '.xlsx'):
            add('legacy_' + path.stem, path, '历史 Weber 快照 · ' + path.stem,
                folder='历史资料/Weber core15 独立快照', source='core15_closeout_2026-10-31')
    for path in sorted((REPO / 'test/inputs').rglob('*')):
        if path.is_file():
            add('regression_' + sha256(path.relative_to(REPO).as_posix().encode()).hexdigest()[:12], path,
                '回归输入 · ' + path.parent.name + ' · ' + path.stem,
                folder='回归资料/默认不导入', source='original_regression', default=False)

    manifest = dict(schema=1, pack='workbench_assets_2026-11-01', simulated=True, baseline='d853ddf',
                    generatedAt=DATE, entries=entries, scenarios=SCENARIOS,
                    invariants=['No artifacts, revisions, approvals, payments or production releases are seeded.',
                                'Legacy Weber snapshots and old Nordlicht wiki facts are not merged into new Cases.',
                                'Future event evidence is attached only through the named event command.',
                                'Line allocation is newly simulated, not extracted from the legacy flat quote.',
                                'CNY 50/53 are conditional cost scopes; inspection/export customs are unknown.'],
                    expected=dict(cost_v1='50.00', quote_v1='8.69', total_v1='26070.00',
                                  cost_v2='53.00', quote_v2='9.21', total_v2='27630.00',
                                  deposit_v2='8289.00', balance_v2='19341.00',
                                  packing_v2=dict(pcsPerCarton=2, cartons=1500)))
    write_json(PACK / 'manifest.json', manifest)
    with zipfile.ZipFile(REPO / 'test/NavoWork_demo_assets.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(PACK / 'manifest.json', 'test/workbench_demo/manifest.json')
        for e in entries:
            archive.write(REPO / e['path'], e['path'])
        for name in ['README.md', 'AUDIT.md', 'VALIDATION.md']:
            path = PACK / name
            if path.exists():
                archive.write(path, f'test/workbench_demo/{name}')
        for name in ['seed_workbench_demo.py', 'validate_workbench_demo.py', 'workbench_demo_content.py']:
            path = REPO / 'test/scripts' / name
            if path.exists():
                archive.write(path, f'test/scripts/{name}')
        archive.write(REPO / 'test/.gitattributes', 'test/.gitattributes')
        for name in ['sheet-recalculation.json', 'validation.json', 'asset-library.png']:
            path = REPO / 'test/.qa/workbench_demo' / name
            if path.exists():
                archive.write(path, f'test/.qa/workbench_demo/{name}')
    print(json.dumps({'assets': len(entries), 'default_assets': sum(e['defaultImport'] for e in entries),
                      'scenarios': len(SCENARIOS)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--finalize', action='store_true')
    args = parser.parse_args()
    finalize() if args.finalize else generate()
