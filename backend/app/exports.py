from __future__ import annotations

import html
import io
import json
import zipfile

from fastapi import Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .core import create_item, decode, encode, fail, item_view, items, require_case, store_blob, uid
from .models import Blob, Case, Item, User, now


def _manifest(db: Session, case: Case, body: dict):
    if body.get("bundleId"):
        bundle = db.get(Item, body["bundleId"])
        if not bundle or bundle.case_id != case.id or bundle.kind != "bundle":
            fail("NOT_FOUND", "材料清单不存在", 404)
        return item_view(bundle)
    return body


def _compose(case: Case, revision: dict, drafts: list[dict], fmt: str, mode: str = "draft") -> tuple[bytes, str, str]:
    title = decode(case.payload).get("title", case.id)
    label = "已批准指定版本" if mode == "formal" else "草稿"
    lines = [f"{title} · V{revision['number']} · {label}", f"客户：{decode(case.payload).get('customer', '')}", f"产品：{revision['requirements'].get('requestedProduct') or '待确认'}", f"数量：{revision['requirements'].get('quantity') or '待确认'}", "本文件未发送；对外发送仍需人工操作。"]
    quote = revision.get("quote")
    if quote:
        lines.append(f"商品小计：USD {quote['goodsSubtotalMinor']/100:.2f}，运费和税费待确认")
    lines += [f"{d['locale']} 回复草稿 V{d['draftVersion']}\n{d['text']}" for d in drafts]
    lines += [f"待确认：{r['message']}" for r in revision.get("risks", [])]
    if fmt == "html":
        content = "<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>" + html.escape(title) + "</title><style>body{font:16px sans-serif;max-width:900px;margin:40px auto;line-height:1.7;padding:20px}pre{white-space:pre-wrap}</style><h1>" + html.escape(title) + "</h1><p>" + html.escape(label) + " · 未发送 · 固定版本</p>" + "".join("<pre>" + html.escape(line) + "</pre>" for line in lines) + "</html>"
        return content.encode("utf-8"), "text/html; charset=utf-8", f"Navowork-{case.id}-V{revision['number']}.html"
    if fmt == "xlsx":
        from openpyxl import Workbook
        book = Workbook()
        sheet = book.active
        sheet.title = "成果摘要"
        for index, line in enumerate(lines, 1):
            sheet.cell(index, 1, line if not line.startswith(("=", "+", "-", "@")) else "'" + line)
        sheet.column_dimensions["A"].width = 100
        buffer = io.BytesIO()
        book.save(buffer)
        return buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"Navowork-{case.id}-V{revision['number']}.xlsx"
    if fmt == "pdf":
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfgen import canvas
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        buffer = io.BytesIO()
        page = canvas.Canvas(buffer)
        page.setFont("STSong-Light", 11)
        y = 800
        for line in lines:
            for piece in line.splitlines():
                if y < 50:
                    page.showPage()
                    page.setFont("STSong-Light", 11)
                    y = 800
                page.drawString(40, y, piece[:90])
                y -= 18
        page.save()
        return buffer.getvalue(), "application/pdf", f"Navowork-{case.id}-V{revision['number']}.pdf"
    if fmt == "zip":
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            pdf, _, _ = _compose(case, revision, drafts, "pdf", mode)
            xlsx, _, _ = _compose(case, revision, drafts, "xlsx", mode)
            zip_file.writestr("quotation-draft.pdf", pdf)
            zip_file.writestr("summary.xlsx", xlsx)
            zip_file.writestr("manifest.json", encode({"caseId": case.id, "revision": revision["number"], "draftVersions": {d["locale"]: d["draftVersion"] for d in drafts}}))
        return buffer.getvalue(), "application/zip", f"Navowork-{case.id}-V{revision['number']}.zip"
    fail("INVALID_INPUT", "导出格式不支持")


def create_export(db: Session, case: Case, body: dict):
    manifest = _manifest(db, case, body)
    number = int(manifest.get("revision", 0))
    rev = next((item_view(i) for i in items(db, "revision", case_id=case.id) if i.version == number), None)
    if not rev:
        fail("NOT_FOUND", "业务版本不存在", 404)
    drafts = []
    for locale, version in (manifest.get("draftVersions") or {}).items():
        row = next((i for i in items(db, "draft", case_id=case.id, parent_id=f"{case.id}:{number}:{locale}") if i.version == int(version)), None)
        if not row:
            fail("NOT_FOUND", "草稿版本不存在", 404)
        drafts.append(item_view(row))
    if not drafts:
        fail("INVALID_INPUT", "至少选择一份草稿")
    mode = body.get("mode", "draft")
    if mode == "formal":
        quote_versions = [i for i in items(db, "artifact", case_id=case.id) if decode(i.payload).get("kind") == "quotation"]
        current_quote = max(quote_versions, key=lambda i: i.version) if quote_versions else None
        approved = any(item_view(i).get("scope") == "commercial_quotation_approval" and item_view(i).get("targetVersionId") == (current_quote.id if current_quote else None) and item_view(i).get("decision") == "approved" for i in items(db, "approval", case_id=case.id))
        pending_change = any(item_view(i).get("status") not in ("applied", "rejected", "cancelled") for i in items(db, "change_set", case_id=case.id))
        if not approved or number != case.current_revision or pending_change or not rev.get("quote"):
            fail("APPROVAL_REQUIRED", "正式报价须有当前版本的核价、商业批准且无待处理变更", 422)
    fmt = body.get("format", "html")
    data, media, filename = _compose(case, rev, drafts, fmt, mode)
    blob = store_blob(db, data, filename, media, case.id)
    export_id = uid("export")
    value = {"exportId": export_id, "status": "ready", "downloadUrl": f"/api/v1/workspaces/{case.workspace_id}/exports/{export_id}/download", "caseId": case.id, "revision": number, "draftVersions": manifest["draftVersions"], "format": fmt, "mode": mode, "blobId": blob.id, "createdAt": now()}
    create_item(db, "export", value, case_id=case.id, item_id=export_id)
    db.commit()
    return value


def export_route(db: Session, user: User, parts: list[str], request: Request):
    if len(parts) < 2:
        fail("NOT_FOUND", "导出不存在", 404)
    row = db.get(Item, parts[1])
    if not row or row.kind != "export":
        fail("NOT_FOUND", "导出不存在", 404)
    require_case(db, user, row.case_id)
    value = item_view(row)
    if len(parts) == 2:
        return value
    if parts[2] == "download":
        blob = db.get(Blob, value["blobId"])
        if not blob:
            fail("NOT_FOUND", "导出文件不存在", 404)
        return FileResponse(blob.path, media_type=blob.media_type, filename=blob.filename,
                            headers={"X-Artifact-Freshness": str((value.get("freshness") or {}).get("status") or value.get("status") or "ready")})
    fail("NOT_FOUND", "接口不存在", 404)


def export_artifact(db: Session, case: Case, artifact: Item, fmt: str, *, commit: bool = True):
    """Render one immutable artifact version; exports remain draft until a separate approval."""
    value = item_view(artifact)
    freshness = value.get("freshness") or {}
    if freshness.get("status") in ("stale", "needs_review", "superseded"):
        fail("STALE_ARTIFACT", "成果输入已变化，请先更新或复核当前版本", 409)
    if value.get("agentRecord"):
        # Reuse the bytes bound to this exact artifact snapshot, never re-render internal JSON for a customer.
        bound = [item_view(i) for i in items(db, "export", case_id=case.id)
                 if item_view(i).get("artifactVersionId") == artifact.id and item_view(i).get("format") == fmt]
        if bound:
            return bound[-1]
        fail("EXPORT_NOT_AVAILABLE", "该成果版本尚无此格式；请重试对应文件导出分支", 422)
    kind = value.get("kind")
    title = "Pro forma invoice" if kind == "order" else str(value.get("title") or kind)
    content = value.get("content") or {}
    if not isinstance(content, dict):
        fail("INVALID_INPUT", "成果内容必须是结构化对象")
    audience = "internal"
    # Rebuild customer files from public values; never hide internal columns in
    # an otherwise internal workbook or serialize arbitrary provenance metadata.
    if kind == "quotation":
        public = ("product", "quantity", "unitPriceUsd", "totalUsd", "currency", "incoterm", "incotermsVersion",
                  "namedPlace", "paymentTerms", "validUntil", "moq", "sampleTime", "productionTime", "exclusions")
        projected = {key: content[key] for key in public if key in content and not isinstance(content[key], (dict, list))}
        if isinstance(content.get("exclusions"), list):
            projected["exclusions"] = [text for text in content["exclusions"] if isinstance(text, str)]
        content = projected
        audience = "customer"
    elif kind == "order":
        public = ("number", "invoiceNumber", "date", "seller", "buyer", "product", "quantity", "unitPriceUsd",
                  "totalUsd", "currency", "incoterm", "incotermsVersion", "namedPlace", "paymentTerms", "validUntil")
        pi = content.get("pi") or {}
        # Party records also have an explicit disclosure boundary.
        content = {key: pi[key] for key in public if key in pi and not isinstance(pi[key], (dict, list))}
        for party in ("seller", "buyer"):
            if isinstance(pi.get(party), dict):
                content[party] = {key: pi[party][key] for key in ("name", "address", "email", "phone")
                                  if key in pi[party] and not isinstance(pi[party][key], (dict, list))}
        audience = "customer"
    def flatten(values, prefix=""):
        for key, cell in values.items():
            locator = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(cell, dict) and cell:
                yield from flatten(cell, locator)
            else:
                yield locator, json.dumps(cell, ensure_ascii=False) if isinstance(cell, (dict, list, bool)) else str(cell) if cell is not None else "待确认"

    rows = list(flatten(content))
    if fmt == "html":
        table = "".join(f"<tr><th>{html.escape(key)}</th><td>{html.escape(cell)}</td></tr>" for key, cell in rows)
        data = f"<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>{html.escape(title)}</title><style>body{{font:16px sans-serif;max-width:960px;margin:40px auto}}th,td{{border:1px solid #ccc;padding:8px;text-align:left;vertical-align:top}}table{{border-collapse:collapse;width:100%}}</style><h1>{html.escape(title)}</h1><p>草稿 · 固定成果版本 V{artifact.version} · 未发送</p><table>{table}</table></html>".encode()
        media = "text/html; charset=utf-8"
    elif fmt == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font
        book = Workbook()
        sheet = book.active
        sheet.title = "成果明细"
        literal = lambda cell: "'" + cell if isinstance(cell, str) and cell.startswith(("=", "+", "-", "@")) else cell
        if kind == "bom":
            sheet.title = "BOM"
            columns = ["category", "item", "spec", "quantityPerPiece", "unit", "supplier", "unitPriceCny", "wastage", "sourceId"]
            sheet.append(columns)
            for row in content.get("rows", []):
                sheet.append([literal(row.get(key)) for key in columns])
        else:
            sheet.append(["字段", "值"])
            for key, cell in rows:
                sheet.append([key, literal(cell)])
        sheet.column_dimensions["A"].width = 30
        sheet.column_dimensions["B"].width = 80
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        buffer = io.BytesIO()
        book.save(buffer)
        data, media = buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif fmt == "docx":
        from docx import Document
        document = Document()
        document.add_heading(title, level=1)
        document.add_paragraph(f"Draft · V{artifact.version} · Not sent")
        table = document.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text, table.rows[0].cells[1].text = "Field", "Value"
        for key, cell in rows:
            cells = table.add_row().cells
            cells[0].text, cells[1].text = key, cell
        buffer = io.BytesIO()
        document.save(buffer)
        data, media = buffer.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif fmt == "pdf":
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfgen import canvas
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        buffer = io.BytesIO()
        page = canvas.Canvas(buffer)
        page.setFont("STSong-Light", 11)
        y = 800
        for line in [title, f"草稿 · V{artifact.version} · 未发送", *[f"{key}: {cell}" for key, cell in rows]]:
            for start in range(0, len(line), 80):
                if y < 50:
                    page.showPage()
                    page.setFont("STSong-Light", 11)
                    y = 800
                page.drawString(40, y, line[start:start + 80])
                y -= 18
        page.save()
        data, media = buffer.getvalue(), "application/pdf"
    else:
        fail("INVALID_INPUT", "成果导出格式不支持")
    filename = f"Navowork-{case.id}-{value['kind']}-V{artifact.version}.{fmt}"
    blob = store_blob(db, data, filename, media, case.id)
    export_id = uid("export")
    result = {"exportId": export_id, "status": "ready", "downloadUrl": f"/api/v1/workspaces/{case.workspace_id}/exports/{export_id}/download", "caseId": case.id, "artifactVersionId": artifact.id, "format": fmt, "mode": "draft", "blobId": blob.id, "createdAt": now()}
    result.update(consistencyId=value.get("consistencyId"), inputSnapshotHash=value.get("inputSnapshotHash"))
    result["templateVersion"] = "bom-rows-v1" if kind == "bom" and fmt == "xlsx" else "field-table-v1"
    result["audience"] = audience
    create_item(db, "export", result, case_id=case.id, item_id=export_id)
    if commit:
        db.commit()
    return result
