"""Render the 15-category mock extension without changing the original fixtures."""
from pathlib import Path
from email.message import EmailMessage
from email import policy
from email.utils import format_datetime
from datetime import datetime
from hashlib import sha256
from html import escape
from functools import partial
import json

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'core15'
QA = ROOT / '.qa' / 'core15'
CASE = 'BAG-2026-DE-001'
SNAPSHOT = 'core15_closeout_2026-10-31'


def font_setup():
    try:
        pdfmetrics.registerFont(TTFont('BodyCJK', r'C:\Windows\Fonts\msyh.ttc', subfontIndex=0))
        pdfmetrics.registerFont(TTFont('BoldCJK', r'C:\Windows\Fonts\msyhbd.ttc', subfontIndex=0))
    except Exception:
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        return 'STSong-Light', 'STSong-Light'
    return 'BodyCJK', 'BoldCJK'


BODY, BOLD = font_setup()
STYLES = {
    'title': ParagraphStyle('title', fontName=BOLD, fontSize=20, leading=28, textColor=colors.HexColor('#17324D'), spaceAfter=4, wordWrap='CJK'),
    'english': ParagraphStyle('english', fontName='Helvetica', fontSize=11, leading=15, textColor=colors.HexColor('#4A657E'), spaceAfter=12),
    'meta': ParagraphStyle('meta', fontName=BODY, fontSize=8.3, leading=12, textColor=colors.HexColor('#486075'), wordWrap='CJK'),
    'section': ParagraphStyle('section', fontName=BOLD, fontSize=11, leading=16, spaceBefore=13, spaceAfter=6, textColor=colors.HexColor('#17324D'), keepWithNext=True, wordWrap='CJK'),
    'label': ParagraphStyle('label', fontName=BODY, fontSize=9, leading=13.5, textColor=colors.HexColor('#25435E'), wordWrap='CJK'),
    'body': ParagraphStyle('body', fontName=BODY, fontSize=9, leading=13.5, textColor=colors.HexColor('#263A49'), wordWrap='CJK'),
    'small': ParagraphStyle('small', fontName=BODY, fontSize=8, leading=12, textColor=colors.HexColor('#5D6F7C'), wordWrap='CJK'),
}


def para(value, style='body'):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return Paragraph(escape(str(value)).replace('\n', '<br/>'), STYLES[style])


def page_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(BODY, 7.5)
    canvas.setFillColor(colors.HexColor('#647687'))
    canvas.drawString(42, 23, 'SIMULATED / 全部虚构模拟数据   |   ' + CASE)
    canvas.drawRightString(A4[0] - 42, 23, f'{doc.page}')
    canvas.restoreState()


def render_doc(path, item, category):
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=42, rightMargin=42,
                            topMargin=36, bottomMargin=40, title=item.get('title_zh', category['title_zh']),
                            author='TradeWorkbench Demo', subject='SIMULATED business fixture')
    title_zh = item.get('title_zh', category['title_zh'])
    title_en = item.get('title_en', category['title_en'])
    story = [para('SIMULATED MOCK / 虚构演示资料', 'small'), Spacer(1, 9),
             para(title_zh, 'title'), para(title_en, 'english')]
    doc_id = item.get('document_id', f'CORE15-{category["id"]:02d}-V3')
    status = item.get('status', '模拟资料 / SIMULATED')
    story += [para(f'Case: {CASE}    文档编号: {doc_id}    日期: 2026-10-31', 'meta'),
              para(f'阶段: {SNAPSHOT}    状态: {status}', 'meta'), Spacer(1, 7)]
    for section in item['sections']:
        story.append(para(section['title'], 'section'))
        rows = [[para(k, 'label'), para(v)] for k, v in section['rows']]
        table = Table(rows, colWidths=[134, A4[0] - 84 - 134], hAlign='LEFT')
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#EDF2F7')),
            ('LINEBELOW', (0, 0), (-1, -1), .35, colors.HexColor('#D6E1EA')),
            ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 4 if category['id'] == 15 else 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 4 if category['id'] == 15 else 6),
        ]))
        story.append(table)
    if item.get('evidence_ids'):
        story += [para('来源与版本', 'section'), para('证据: ' + ', '.join(item['evidence_ids']), 'small')]
    story += [Spacer(1, 12), para('所有主体、报价、检验结果和批准均为虚构模拟记录。该阶段不代表收到货款、正式生产放行或工厂已经开工。', 'small')]
    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer, canvasmaker=partial(Canvas, invariant=1))


def main():
    data = json.loads((ROOT / 'scripts' / 'core15_content.json').read_text(encoding='utf-8-sig'))
    OUT.mkdir(exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    evidence_dir = OUT / 'evidence'
    evidence_dir.mkdir(exist_ok=True)
    evidence_records = []
    for e in data['evidence']:
        if e.get('generate') is False or e.get('existing_path'):
            original = ROOT / e['existing_path']
            copied = evidence_dir / ('original-' + original.name)
            copied.write_bytes(original.read_bytes())
            evidence_records.append({'id': e['id'], 'path': 'evidence/' + copied.name, 'original_path': e['existing_path'], 'sha256': sha256(original.read_bytes()).hexdigest(), 'existing_source': True})
            continue
        msg = EmailMessage(policy=policy.SMTP)
        msg['From'] = e['from']
        msg['To'] = e['to']
        msg['Subject'] = e['subject']
        msg['Date'] = format_datetime(datetime.fromisoformat(e['datetime']))
        msg['Message-ID'] = e.get('message_id', f'<{e["id"]}@core15-demo.invalid>')
        msg['X-Demo-Data'] = 'SIMULATED'
        msg['X-Demo-Snapshot'] = SNAPSHOT
        msg.set_content(e['body'] + '\n\nSIMULATED EVIDENCE: all events and approvals are fictional.\n')
        p = evidence_dir / e['filename']
        p.write_bytes(msg.as_bytes())
        alias = f'E{1 + sum(not r.get("existing_source", False) for r in evidence_records):02d}'
        evidence_records.append({'id': e['id'], 'alias': alias, 'source_id': e.get('source_id'), 'path': 'evidence/' + p.name, 'sha256': sha256(p.read_bytes()).hexdigest(), 'datetime': e['datetime'], 'scope': e.get('scope')})
    mapping = []
    for category in data['categories']:
        files = []
        if category['id'] in (8, 9):
            files = [category['filename']]
        else:
            for item in category.get('documents', [category]):
                name = item['filename']
                render_doc(OUT / name, item, category)
                files.append(name)
        mapping.append({'id': category['id'], 'name_zh': category['title_zh'], 'name_en': category['title_en'], 'files': files})
    manifest = {
        'schema_version': 'tradeworkbench-core15/v1', 'case_id': CASE, 'snapshot': SNAPSHOT,
        'simulation_only': True, 'previous_snapshot_preserved': 'test/cases/BAG-2026-DE-001.json',
        'versions': {'tech_pack': 'V3', 'quotation': 'V3', 'sample': 'S03', 'po': 'DE-PO-2026-118-R2', 'pi': 'PI-26031-003', 'sc': 'SC-26031-003', 'technical_annex': 'V3'},
        'commercial': {'quantity_pcs': 3000, 'unit_price_usd': '9.21', 'total_usd': '27630.00', 'deposit_due_usd': '8289.00', 'balance_due_usd': '19341.00', 'deposit_received': None},
        'gates': {'sample_approval': 'approved_simulated_S03_only', 'price_approval': 'approved_simulated_V3_price_only', 'external_send': 'not_connected', 'order_execution': 'blocked_pending_contract_signature', 'production_release': 'blocked', 'production_blockers': ['PI/SC not signed', 'deposit receipt not evidenced', 'internal production release approval missing']},
        'categories': mapping, 'evidence': evidence_records,
    }
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# 15 类核心业务文件 Mock', '', '全部属于虚构模拟 Case `BAG-2026-DE-001`。这是 2026-10-31 的后续确认阶段，原测试包的缺项与阻断场景保持原样。', '',
             '新增证据在 `evidence/`。按编号可逐份上传；不要把 `manifest.json` 或脚本当作原始客户资料上传。', '',
             '| 编号 | 核心类别 | 实际文件 |', '| --- | --- | --- |']
    for row in mapping:
        links = '、'.join(f'[{Path(f).stem}]({f})' for f in row['files'])
        lines.append(f'| {row["id"]:02d} | {row["name_zh"]} | {links} |')
    lines += ['', '## 证据索引', '', '| 简称 | 证据文件 |', '| --- | --- |']
    lines += [f'| {e.get("alias", "历史源副本")} | [{Path(e["path"]).name}]({e["path"]}) |' for e in evidence_records]
    lines += ['', '共 6 封新增模拟确认邮件，另保留 3 份历史原始邮件的逐字节副本，便于脱离原目录单独回放。', '', '## 阶段与门禁', '',
              '- 最终规格 Tech Pack V3、报价 V3、样品 S03、PO R2、PI/SC 和技术附件 V3 相互引用。',
              '- 60 mm LOGO、新彩盒规格、MOQ 与候选生产交期来自新增虚构确认邮件；不是从旧图片推测。',
              '- 最终样品确认只批准 S03/Tech Pack V3/包装规格，不能代表货款到账或量产放行。',
              '- PI 和 SC 为待签署草稿；量产仍因缺少订金到账证据与内部生产放行而阻断。',
              '- 45 天到汉堡仍为客户目标。28 天为满足样品、订金、内部放行条件后的候选工厂生产期。', '',
              '## 复建和校验', '',
              '业务内容在 `../scripts/core15_content.json`，PDF/证据生成器为 `../scripts/build_core15.py`，Excel 生成器为 `../scripts/build_core15_sheets.mjs`。',
              '使用 Codex bundled Python/Node（同上级 README）。先运行 PDF 生成器，再运行 Excel 生成器，最后运行 `../scripts/validate_core15.py`。',
              'Excel 生成器通过 `CODEX_NODE_MODULES`（可选）定位 bundled `@oai/artifact-tool`，不会写入项目依赖目录。',
              '重新生成两种文件后先执行 `validate_core15.py --seal` 绑定本次模拟版本哈希，此后执行不带参数的 `validate_core15.py` 只读检查。', '']
    (OUT / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f'Rendered {sum(len(r["files"]) for r in mapping) - 2} PDFs, {sum(not e.get("existing_source", False) for e in evidence_records)} new evidence emails, and 15-category index.')


if __name__ == '__main__':
    main()
