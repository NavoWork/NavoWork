"""Small supported business layouts; no arbitrary Office compatibility claims."""
from io import BytesIO
from html import escape
from decimal import Decimal
from zipfile import ZipFile
from pathlib import Path
import os
import math

from docx import Document
from docx.shared import Inches, Pt
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont

from navowork_agent.tools.pricing import ContentSnapshot, calculate_quote


CLIENT_FIELDS = ("product", "quantity", "packaging", "material", "dimensions", "logo", "incoterm", "named_place", "payment_terms", "requested_arrival", "production_estimate")
FIELD_LABELS = {k: k.replace("_", " ").capitalize() for k in CLIENT_FIELDS}


def display(value):
    return "Unknown" if value is None else str(value)


def client_content(snapshot: ContentSnapshot, pricing: dict):
    # Build from scratch. Never copy internal snapshot, supplier identity, citations or metadata.
    quote = pricing.get("quote")
    return {"fields": {k: display(snapshot.fields[k].value) for k in CLIENT_FIELDS if k in snapshot.fields},
            "quote": {k: quote[k] for k in ("unit_usd", "total_usd")} if quote else None, "status": "Draft for review" if quote else "Pending pricing",
            "disclaimer": "SIMULATED — commercial draft; production, MOQ and arrival commitments require confirmation."}


def _style_sheet(ws):
    ws.freeze_panes = "B2"
    ws.column_dimensions["A"].width = 32
    for col in ("B", "C", "D", "E"):
        ws.column_dimensions[col].width = 28
    for cell in ws[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill("solid", fgColor="16324F")
    for row in ws:
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.row_dimensions[row[0].row].height = max(22, 15 * max(math.ceil(len(str(c.value or "")) / max(10, ws.column_dimensions[c.column_letter].width)) for c in row))
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.print_options.horizontalCentered = True
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0


def render_spec(snapshot: ContentSnapshot, version: int, snapshot_hash: str) -> bytes:
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = sec.bottom_margin = Inches(.7)
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)
    doc.add_paragraph("Product specification draft", "Title")
    doc.add_paragraph(f"SIMULATED | Version {version} | Content {snapshot_hash[:12]}")
    doc.add_paragraph("This draft records sourced requirements. Unknown values and unconfirmed timing remain open.")
    table = doc.add_table(rows=1, cols=2)
    table.style = "Light Shading Accent 1"
    table.rows[0].cells[0].text, table.rows[0].cells[1].text = "Requirement", "Current value"
    for key, fact in snapshot.fields.items():
        cells = table.add_row().cells
        cells[0].text, cells[1].text = key, display(fact.value)
    if snapshot.internal_notes:
        doc.add_paragraph("Working notes", "Heading 1")
        for key, text in snapshot.internal_notes.items():
            doc.add_paragraph(f"{key}: {text}")
    stream = BytesIO()
    doc.save(stream)
    return stream.getvalue()


def render_cost(snapshot: ContentSnapshot, version: int, snapshot_hash: str) -> bytes:
    from navowork_agent.tools.formulas import recalculate_xlsx
    wb = Workbook()
    ws = wb.active
    ws.title = "Cost"
    ws.append(["SIMULATED internal cost", "Value", "Scope", "Source"])
    ws.append(["Version", version])
    ws.append(["Snapshot", snapshot_hash])
    p = snapshot.pricing
    if p is None:
        ws.append(["Pricing", "Unknown"])
    else:
        ws.append(["Quantity", p.quantity])  # B4
        ws.append(["FX CNY per USD", float(p.fx_cny_per_usd.value) if p.fx_cny_per_usd.value is not None else "Unknown"])
        ws.append(["Gross margin ratio", float(p.target_gross_margin.value) if p.target_gross_margin.value is not None else "Unknown"])
        first = 7
        for cost in p.costs:
            row = ws.max_row + 1
            ws.append([cost.category, float(cost.amount.value) if cost.amount.value is not None else "Unknown", cost.scope,
                       "; ".join(f"{s.file_id}:{s.locator}" for s in cost.amount.sources)])
            ws.cell(row, 1).data_type = "s"
            ws.cell(row, 4).data_type = "s"
            ws.cell(row, 5, f"=B{row}/B4" if cost.scope == "per_order" else f"=B{row}")
        calc = calculate_quote(p)
        if calc["quote"]:
            row = ws.max_row + 1
            ws.append(["Cost CNY per unit", f"=SUM(E{first}:E{row-1})"])
            ws.append(["Unit quote USD", f"=ROUNDUP(B{row}/B5/(1-B6),2)"])
            ws.append(["Goods subtotal USD", f"=B{row+1}*B4"])
        else:
            # Unknowns are explicit, with no formula pretending missing values are zero.
            for row in range(first, ws.max_row + 1):
                ws.cell(row, 5, None).value = None
            ws.append(["Status", calc["status"]])
    _style_sheet(ws)
    stream = BytesIO()
    wb.save(stream)
    return recalculate_xlsx(stream.getvalue())


def render_quotation(snapshot: ContentSnapshot, version: int, snapshot_hash: str, fmt: str) -> bytes:
    p = calculate_quote(snapshot.pricing) if snapshot.pricing else {"quote": None}
    view = client_content(snapshot, p)
    rows = [["Customer quotation draft", f"V{version}"], ["Snapshot", snapshot_hash[:12]], ["Status", view["status"]]]
    rows += [[FIELD_LABELS[k], v] for k, v in view["fields"].items()]
    quote = view["quote"]
    if quote:
        rows += [["Currency", "USD"], ["Unit price USD", quote["unit_usd"]], ["Goods subtotal USD", quote["total_usd"]]]
    else:
        rows += [["Unit price USD", "Unknown"], ["Goods subtotal USD", "Unknown"]]
    rows += [["Terms", view["disclaimer"]]]
    stream = BytesIO()
    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = "Quotation"
        for row in rows:
            # Treat all user/source strings as text, never executable spreadsheet formulas.
            ws.append(row)
            for cell in ws[ws.max_row]:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
        _style_sheet(ws)
        ws.column_dimensions["B"].width = 65
        wb.save(stream)
    elif fmt == "pdf":
        font = "Helvetica"
        if any("\u2e80" <= ch <= "\u9fff" for row in rows for cell in row for ch in str(cell)):
            # A real embedded font is required for CJK; never rely on reader-specific CID substitution.
            candidate = os.getenv("NAVOWORK_PDF_FONT") or ("C:/Windows/Fonts/simsun.ttc" if os.name == "nt" else "")
            if not candidate or not Path(candidate).is_file():
                raise ValueError("CJK PDF requires a supported TrueType NAVOWORK_PDF_FONT")
            font = "NavoCJK"
            pdfmetrics.registerFont(TTFont(font, candidate))
        style = ParagraphStyle("body", fontName=font, fontSize=10, leading=15, alignment=TA_LEFT, wordWrap="CJK")
        flow = [Paragraph("Customer quotation draft", ParagraphStyle("title", parent=style, fontSize=20, leading=26)), Spacer(1, 14)]
        table = Table([[Paragraph(escape(str(c)), style) for c in row] for row in rows], colWidths=[155, 340], repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EFF6")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8), ("LINEBELOW", (0, 0), (-1, -1), .4, colors.HexColor("#D6DFE8"))]))
        flow.append(table)
        SimpleDocTemplate(stream, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40).build(flow)
    else:
        raise ValueError("Quotation export supports xlsx and pdf")
    return stream.getvalue()


def verify_output(data: bytes, fmt: str) -> dict:
    if fmt == "docx":
        d = Document(BytesIO(data))
        return {"readable": True, "paragraphs": len(d.paragraphs), "tables": len(d.tables)}
    if fmt == "xlsx":
        formulas = load_workbook(BytesIO(data), data_only=False)
        values = load_workbook(BytesIO(data), data_only=True)
        for ws in formulas:
            for row in ws:
                for cell in row:
                    if cell.data_type == "f" and values[ws.title][cell.coordinate].value is None:
                        raise ValueError(f"Formula cache missing at {ws.title}!{cell.coordinate}")
        formulas.close()
        values.close()
        return {"readable": True, "formula_caches": "present"}
    if fmt == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(data))
        text = "\n".join(p.extract_text() or "" for p in reader.pages)
        if "Customer quotation draft" not in text:
            raise ValueError("PDF text validation failed")
        return {"readable": True, "pages": len(reader.pages), "text": text}
    raise ValueError("Unsupported format")
