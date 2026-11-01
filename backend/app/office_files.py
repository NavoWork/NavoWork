"""Case-scoped basic Office editor. Preview and downloads read identical immutable bytes."""
from __future__ import annotations

import base64
import hashlib
from io import BytesIO
from pathlib import Path
import re
from zipfile import ZipFile
from zipfile import BadZipFile
from copy import deepcopy

from fastapi.responses import FileResponse, Response
from sqlalchemy import text

from .core import create_item, decode, encode, fail, item_view, items, store_blob, uid
from .models import Blob, Item, now

FORMATS = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
           "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
MAX_CELLS = 10000
BOM_COLUMNS = ["category", "item", "spec", "quantityPerPiece", "unit", "supplier", "unitPriceCny", "wastage", "sourceId"]
BOM_NUMBERS = ("quantityPerPiece", "unitPriceCny", "wastage")


def _bytes(db, case, blob_id):
    blob = db.get(Blob, blob_id)
    if not blob or blob.case_id != case.id:
        fail("NOT_FOUND", "文件不属于当前项目", 404)
    data = Path(blob.path).read_bytes()
    if hashlib.sha256(data).hexdigest() != blob.sha256:
        fail("SOURCE_VERSION", "文件校验失败", 409)
    return blob, data


def _source(db, case, file_id):
    row = db.get(Item, str(file_id))
    if not row or row.case_id != case.id or row.kind not in ("evidence", "agent_file", "export"):
        fail("NOT_FOUND", "可编辑来源不存在", 404)
    value = decode(row.payload)
    blob_id = value.get("blobId") or (value.get("ref") or {}).get("file_id")
    blob, data = _bytes(db, case, blob_id)
    if Path(blob.filename).suffix.lower()[1:] not in FORMATS:
        fail("UNSUPPORTED_EDIT_FORMAT", "仅支持 DOCX 和 XLSX 工作副本", 422)
    return row, blob, data


def _row(db, case, document_id, version=None):
    rows = items(db, "office_file", case_id=case.id, parent_id=document_id)
    if version is not None:
        rows = [row for row in rows if row.version == version]
    if not rows:
        fail("NOT_FOUND", "工作副本版本不存在", 404)
    return max(rows, key=lambda row: row.version)


def _validate_package(data):
    # Reject excessive decompression and active/external content before Office parsers run.
    with ZipFile(BytesIO(data)) as archive:
        infos = archive.infolist()
        if len(infos) > 2000 or sum(info.file_size for info in infos) > 60 * 1024 * 1024:
            raise ValueError("Office package exceeds supported size")
        for info in infos:
            name = info.filename.lower()
            if "vbaproject" in name or "externallinks/" in name or "/embeddings/" in name:
                raise ValueError("Macros, embedded files and external workbooks are unsupported")


def _normalize(data, fmt):
    _validate_package(data)
    if fmt == "xlsx":
        from navowork_agent.tools.formulas import recalculate_xlsx
        return recalculate_xlsx(data)
    from docx import Document
    document = Document(BytesIO(data))
    if len(document.paragraphs) > 2000 or sum(len(table.rows) * len(table.columns) for table in document.tables) > MAX_CELLS:
        raise ValueError("Document exceeds editor limits")
    return data


def preview(data, fmt):
    _validate_package(data)
    if fmt == "docx":
        from docx import Document
        document = Document(BytesIO(data))
        paragraphs = [{"index": i, "text": paragraph.text, "style": paragraph.style.name,
                       "bold": bool(paragraph.runs and paragraph.runs[0].bold),
                       "italic": bool(paragraph.runs and paragraph.runs[0].italic)}
                      for i, paragraph in enumerate(document.paragraphs)]
        tables = [{"index": i, "rows": [[cell.text for cell in row.cells] for row in table.rows]}
                  for i, table in enumerate(document.tables)]
        images = []
        for i, shape in enumerate(document.inline_shapes):
            embed = shape._inline.graphic.graphicData.pic.blipFill.blip.embed
            part = document.part.related_parts[embed]
            if part.content_type in ("image/png", "image/jpeg") and len(part.blob) < 5 * 1024 * 1024:
                images.append({"index": i, "url": f"data:{part.content_type};base64," + base64.b64encode(part.blob).decode(),
                               "width": round(shape.width / 914400, 2)})
        return {"format": fmt, "paragraphs": paragraphs, "tables": tables, "images": images,
                "notice": "基础内容预览；分页、页眉页脚与复杂排版请下载原生文件检查。"}
    from openpyxl import load_workbook
    book = load_workbook(BytesIO(data), data_only=False)
    values = load_workbook(BytesIO(data), data_only=True)
    if sum(sheet.max_row * sheet.max_column for sheet in book) > MAX_CELLS:
        raise ValueError("Workbook exceeds 10,000-cell editor limit")
    sheets = []
    for sheet in book:
        cells = []
        for row in sheet:
            cells.append([{"address": cell.coordinate, "value": cell.value,
                           "display": values[sheet.title][cell.coordinate].value,
                           "formula": cell.data_type == "f", "bold": bool(cell.font.bold),
                           "numberFormat": cell.number_format} for cell in row])
        sheets.append({"name": sheet.title, "rows": cells})
    book.close()
    values.close()
    return {"format": fmt, "sheets": sheets,
            "notice": "支持同表相对引用、四则运算、SUM、ROUND、ROUNDUP；外链、绝对/跨表引用和复杂公式会被拒绝。"}


def _image(db, case, file_id):
    row = db.get(Item, str(file_id))
    if not row or row.case_id != case.id or row.kind not in ("evidence", "export"):
        raise ValueError("Select an image uploaded or generated in this Case")
    blob, data = _bytes(db, case, decode(row.payload).get("blobId"))
    if blob.media_type not in ("image/png", "image/jpeg"):
        raise ValueError("Only PNG/JPEG images are supported")
    from PIL import Image
    with Image.open(BytesIO(data)) as image:
        if image.width * image.height > 25_000_000:
            raise ValueError("Image exceeds supported resolution")
        image.verify()
    return data


def apply_edits(db, case, data, fmt, operations):
    if not isinstance(operations, list) or not 1 <= len(operations) <= 200:
        raise ValueError("Provide 1–200 edit operations")
    buffer = BytesIO()
    if fmt == "docx":
        from docx import Document
        from docx.shared import Inches, Pt
        document = Document(BytesIO(data))
        for op in operations:
            kind = op.get("op")
            for key in ("index", "table", "row", "column"):
                if key in op and (not isinstance(op[key], int) or isinstance(op[key], bool) or op[key] < 0):
                    raise ValueError("Document edit indices must be non-negative integers")
            if kind in ("set_paragraph", "append_paragraph"):
                value = str(op.get("text", ""))
                if len(value) > 10000:
                    raise ValueError("Paragraph exceeds supported size")
                paragraph = document.add_paragraph(value) if kind == "append_paragraph" else document.paragraphs[int(op["index"])]
                if kind == "set_paragraph":
                    paragraph.text = value
                if op.get("style") in ("Normal", "Title", "Heading 1", "Heading 2"):
                    paragraph.style = op["style"]
                for run in paragraph.runs:
                    for key in ("bold", "italic"):
                        if key in op:
                            setattr(run, key, bool(op[key]))
                    if "fontSize" in op:
                        run.font.size = Pt(max(6, min(72, float(op["fontSize"]))))
            elif kind == "set_table_cell":
                document.tables[int(op["table"])].cell(int(op["row"]), int(op["column"])).text = str(op.get("text", ""))[:10000]
            elif kind == "add_table":
                rows, columns = int(op.get("rows", 2)), int(op.get("columns", 2))
                if not 1 <= rows <= 50 or not 1 <= columns <= 20:
                    raise ValueError("Table dimensions exceed supported bounds")
                document.add_table(rows=rows, cols=columns, style="Table Grid")
            elif kind in ("add_picture", "replace_picture"):
                image = _image(db, case, op.get("fileId"))
                if kind == "add_picture":
                    document.add_picture(BytesIO(image), width=Inches(max(.1, min(6, float(op.get("width", 3))))))
                else:
                    shape = document.inline_shapes[int(op["index"])]
                    rid, _ = document.part.get_or_add_image(BytesIO(image))
                    shape._inline.graphic.graphicData.pic.blipFill.blip.embed = rid
            else:
                raise ValueError("Unsupported DOCX operation")
        document.save(buffer)
    else:
        from openpyxl import load_workbook
        book = load_workbook(BytesIO(data))
        for op in operations:
            sheet = book[str(op["sheet"])]
            kind = op.get("op")
            if kind == "set_cell":
                address = str(op.get("cell", ""))
                if not re.fullmatch(r"[A-Z]{1,3}[1-9][0-9]{0,4}", address):
                    raise ValueError("Invalid cell address")
                value = op.get("value")
                if value is not None and not isinstance(value, (str, int, float, bool)):
                    raise ValueError("Invalid cell value")
                sheet[address] = value
                if isinstance(value, str) and not op.get("formula", False):
                    sheet[address].data_type = "s"
                if "bold" in op:
                    from copy import copy
                    font = copy(sheet[address].font)
                    font.bold = bool(op["bold"])
                    sheet[address].font = font
            elif kind == "copy_range":
                from copy import copy
                from openpyxl.formula.translate import Translator
                from openpyxl.utils.cell import range_boundaries, coordinate_to_tuple
                source_range = str(op.get("sourceRange", ""))
                destination = str(op.get("cell", ""))
                if not re.fullmatch(r"[A-Z]{1,3}[1-9][0-9]{0,4}:[A-Z]{1,3}[1-9][0-9]{0,4}", source_range) or not re.fullmatch(r"[A-Z]{1,3}[1-9][0-9]{0,4}", destination):
                    raise ValueError("Use ranges like A1:B3 and target cell D1")
                left, top, right, bottom = range_boundaries(source_range)
                target_row, target_column = coordinate_to_tuple(destination)
                if (right - left + 1) * (bottom - top + 1) > 1000:
                    raise ValueError("Copy range exceeds 1,000-cell limit")
                cells = [(cell.row - top, cell.column - left, cell.coordinate, cell.value, copy(cell._style), cell.data_type)
                         for row in sheet.iter_rows(min_row=top, max_row=bottom, min_col=left, max_col=right) for cell in row]
                for offset_row, offset_column, origin, value, style, data_type in cells:
                    target = sheet.cell(target_row + offset_row, target_column + offset_column)
                    target.value = Translator(value, origin=origin).translate_formula(target.coordinate) if data_type == "f" else value
                    target._style = style
                    if data_type == "s":
                        target.data_type = "s"
            elif kind in ("insert_blank_rows", "insert_blank_cols", "delete_rows", "delete_cols"):
                if any(cell.data_type == "f" for sh in book for row in sh for cell in row):
                    raise ValueError("Structural edits on formula workbooks require manual review")
                index, count = int(op["index"]), int(op.get("count", 1))
                if not 1 <= index <= 10000 or not 1 <= count <= 100:
                    raise ValueError("Invalid row/column bounds")
                method = {"insert_blank_rows": "insert_rows", "insert_blank_cols": "insert_cols"}.get(kind, kind)
                getattr(sheet, method)(index, count)
            else:
                raise ValueError("Unsupported XLSX operation")
        book.save(buffer)
        book.close()
    return _normalize(buffer.getvalue(), fmt)


def _template_cells(data, fmt):
    """Read only the canonical server-generated field/value table, never infer semantics."""
    if fmt == "docx":
        from docx import Document
        document = Document(BytesIO(data))
        if len(document.tables) != 1:
            raise ValueError("The registered field table was added or removed")
        table = document.tables[0]
        rows = [[cell.text for cell in row.cells] for row in table.rows]
        location = {"table": 0}
    else:
        from openpyxl import load_workbook
        book = load_workbook(BytesIO(data), data_only=False)
        if len(book.worksheets) != 1:
            book.close()
            raise ValueError("The registered worksheet layout changed")
        sheet = book.active
        if sheet.max_column != 2:
            book.close()
            raise ValueError("The registered field/value columns changed")
        rows = [[cell.value for cell in row] for row in sheet]
        location = {"sheet": sheet.title}
        book.close()
    if not rows or rows[0] not in (["Field", "Value"], ["字段", "值"]):
        raise ValueError("The registered table header changed")
    if any(len(row) != 2 or not isinstance(row[0], str) for row in rows):
        raise ValueError("The registered field labels changed")
    labels = [row[0] for row in rows]
    if len(set(labels[1:])) != len(labels[1:]):
        raise ValueError("Duplicate field labels are not a safe mapping")
    return {"location": location, "labels": labels,
            "values": {row[0]: row[1] for row in rows[1:]},
            "locators": {row[0]: ({"table": 0, "row": index, "column": 1} if fmt == "docx" else
                                    {"sheet": location["sheet"], "cell": f"B{index + 1}"})
                         for index, row in enumerate(rows[1:], 1)}}


def _bom_cells(data):
    from openpyxl import load_workbook
    book = load_workbook(BytesIO(data), data_only=False)
    try:
        if len(book.worksheets) != 1 or book.active.title != "BOM":
            raise ValueError("BOM 工作表布局发生变化，未覆盖业务数据。")
        sheet = book.active
        if sheet.max_column != len(BOM_COLUMNS) or [cell.value for cell in sheet[1]] != BOM_COLUMNS:
            raise ValueError("BOM 字段列发生变化，未覆盖业务数据。")
        if any(cell.data_type == "f" for row in sheet for cell in row):
            raise ValueError("BOM 字段映射暂不自动采用公式；文件已保存，需核对业务值。")
        return [{key: cell.value for key, cell in zip(BOM_COLUMNS, row)}
                for row in sheet.iter_rows(min_row=2)]
    finally:
        book.close()


def _scalar(value):
    return "" if value is None else str(value)


def _freeze_mapping(db, case, source_row, data, fmt):
    if source_row.kind != "export":
        return None
    from .domain import SPEC_KEYS
    from .workbench import latest_artifact
    export = decode(source_row.payload)
    if fmt == "xlsx" and export.get("templateVersion") == "bom-rows-v1":
        artifact = latest_artifact(db, case, "bom")
        if not artifact or export.get("artifactVersionId") != artifact["itemId"]:
            return None
        try:
            rows = _bom_cells(data)
        except ValueError:
            return None
        baseline = artifact.get("content", {}).get("rows", [])
        if len(rows) != len(baseline) or any(_scalar(row.get(key)) != _scalar(original.get(key))
            for row, original in zip(rows, baseline) for key in BOM_COLUMNS):
            return None
        return {"ruleVersion": "office-bom-row-map-v1", "artifactId": artifact["itemId"], "kind": "bom",
                "artifactVersion": artifact["version"], "rows": rows,
                "fields": {f"rows.{index}.{key}": {"sheet": "BOM", "cell": f"{chr(65 + BOM_COLUMNS.index(key))}{index + 2}"}
                           for index in range(len(rows)) for key in BOM_NUMBERS}}
    if export.get("templateVersion") != "field-table-v1":
        return None
    artifact = latest_artifact(db, case, "spec")
    if not artifact or export.get("artifactVersionId") != artifact["itemId"]:
        return None
    try:
        table = _template_cells(data, fmt)
    except ValueError:
        return None
    fields = artifact.get("content", {}).get("fields", {})
    mappings = {}
    for key in SPEC_KEYS:
        path = "fields." + key
        if path not in table["values"] or key not in fields:
            continue
        expected = "待确认" if fields[key] is None else str(fields[key])
        if str(table["values"][path]) != expected:
            return None
        mappings[path] = table["locators"][path]
    if not mappings:
        return None
    return {"ruleVersion": "office-spec-field-map-v1", "artifactId": artifact["itemId"], "kind": "spec",
            "artifactVersion": artifact["version"], "location": table["location"], "labels": table["labels"],
            "values": table["values"], "fields": mappings}


def _reconcile_mapping(db, case, source, data, fmt, operations):
    """Apply registered value cells atomically; keep file labor when mapping cannot safely commit."""
    mapping = source.get("templateMapping")
    if not mapping:
        return source, {"status": "needs_review", "coverageComplete": False}
    from .domain import merge_spec
    from .workbench import append_artifact, commit_revision, latest_artifact
    current = latest_artifact(db, case, mapping["kind"])
    if not current or current["itemId"] != mapping["artifactId"]:
        return source, {"status": "mapping_conflict", "coverageComplete": False,
                        "reason": "业务规格已更新，当前文件已保存为待复核草稿，未覆盖较新业务版本。"}
    if mapping["kind"] == "bom":
        return _reconcile_bom(db, case, source, current, mapping, data, operations)
    try:
        table = _template_cells(data, fmt)
        if table["labels"] != mapping["labels"] or table["location"] != mapping["location"]:
            raise ValueError("字段标签或表格布局已改变，文件已保存为草稿，未覆盖业务字段。")
        changed = {path: value for path, value in table["values"].items()
                   if str(value) != str(mapping["values"].get(path))}
        patch = {}
        for path, value in changed.items():
            if path not in mapping["fields"]:
                continue
            key = path.removeprefix("fields.")
            if key == "quantity":
                if not re.fullmatch(r"[1-9][0-9]{0,8}", str(value)) or int(value) > 100_000_000:
                    raise ValueError("数量必须为有效正整数；编辑内容已保存为待复核文件草稿。")
                value = str(int(value))
            patch[key] = None if value in (None, "待确认") else str(value)
    except (ValueError, KeyError, TypeError) as exc:
        return source, {"status": "mapping_conflict", "coverageComplete": False, "reason": str(exc)}
    controlled = set(changed) <= set(mapping["fields"])
    for operation in operations:
        if fmt == "docx":
            known = operation.get("op") == "set_table_cell" and any(all(operation.get(key) == value for key, value in locator.items()) for locator in mapping["fields"].values())
        else:
            known = operation.get("op") == "set_cell" and any(all(operation.get(key) == value for key, value in locator.items()) for locator in mapping["fields"].values())
        controlled = controlled and known
    artifact = current
    if patch:
        merged = merge_spec(current.get("content"), {"fields": patch})
        artifact = append_artifact(db, case, "spec", merged, title=current.get("title") or "产品规格", status="draft")
        commit_revision(db, case, f"文件编辑同步规格 V{artifact['version']}", node="requirements")
    next_source = deepcopy(source)
    next_source["templateMapping"] = {**mapping, "artifactId": artifact["itemId"], "artifactVersion": artifact["version"],
                                      "values": table["values"]}
    return next_source, {"status": "mapped" if controlled else "needs_review", "coverageComplete": controlled,
                        "artifactId": artifact["itemId"], "artifactVersion": artifact["version"],
                        "changedFields": sorted(patch), "businessConsistencyId": artifact.get("consistencyId")}


def _reconcile_bom(db, case, source, current, mapping, data, operations):
    from decimal import Decimal, InvalidOperation
    from .domain import normalize_bom
    from .workbench import append_artifact, commit_revision
    try:
        rows = _bom_cells(data)
        original_rows = mapping["rows"]
        if len(rows) != len(original_rows):
            raise ValueError("BOM 行数改变，已保存文件草稿，需重新确认行映射。")
        patch_rows = deepcopy(current.get("content", {}).get("rows", []))
        changed = []
        for index, (row, original) in enumerate(zip(rows, original_rows)):
            for key in BOM_COLUMNS:
                if _scalar(row.get(key)) == _scalar(original.get(key)):
                    continue
                if key not in BOM_NUMBERS:
                    raise ValueError("物料、单位或来源等绑定信息改变，已保存草稿，未自动改写成本依据。")
                value = row.get(key)
                if value in (None, ""):
                    patch_rows[index][key] = None
                else:
                    number = Decimal(str(value))
                    if not number.is_finite() or number < 0 or key == "wastage" and number >= 1:
                        raise ValueError("BOM 数值必须非负且损耗为小于 1 的比例；文件草稿已保留。")
                    patch_rows[index][key] = str(number)
                changed.append(f"rows.{index}.{key}")
    except (ValueError, KeyError, TypeError, InvalidOperation) as exc:
        return source, {"status": "mapping_conflict", "coverageComplete": False, "reason": str(exc)}
    controlled = all(operation.get("op") == "set_cell" and not operation.get("formula") and
                     any(all(operation.get(key) == value for key, value in locator.items()) for locator in mapping["fields"].values())
                     for operation in operations)
    artifact = current
    if changed:
        content = {**current.get("content", {}), "rows": normalize_bom(patch_rows)}
        artifact = append_artifact(db, case, "bom", content, title=current.get("title") or "BOM", status="draft")
        commit_revision(db, case, f"文件编辑同步 BOM V{artifact['version']}", node="requirements")
    next_source = deepcopy(source)
    next_source["templateMapping"] = {**mapping, "artifactId": artifact["itemId"], "artifactVersion": artifact["version"], "rows": rows}
    return next_source, {"status": "mapped" if controlled else "needs_review", "coverageComplete": controlled,
                        "artifactId": artifact["itemId"], "artifactVersion": artifact["version"],
                        "changedFields": changed, "businessConsistencyId": artifact.get("consistencyId")}


def _save(db, case, document_id, source, data, name, fmt, version, actor, operations=None):
    mapping_result = {"status": "needs_review", "coverageComplete": False}
    if version == 1 and source.get("templateMapping"):
        mapping_result = {"status": "registered", "coverageComplete": True,
                          "artifactId": source["templateMapping"]["artifactId"],
                          "artifactVersion": source["templateMapping"]["artifactVersion"]}
    if version > 1:
        source, mapping_result = _reconcile_mapping(db, case, source, data, fmt, operations or [])
    blob = store_blob(db, data, f"{Path(name).stem}-v{version}.{fmt}", FORMATS[fmt], case.id)
    payload = {"documentId": document_id, "version": version, "source": source, "blobId": blob.id,
               "format": fmt, "name": name, "sha256": blob.sha256, "createdBy": actor, "createdAt": now(),
               "status": "needs_review", "impactCoverage": "mapped" if mapping_result.get("coverageComplete") else "review_required", "operations": operations or [],
               "fieldMapping": mapping_result,
               "downloadUrl": f"/api/v1/workspaces/{case.workspace_id}/inquiries/{case.id}/workbench/office/{document_id}/versions/{version}/download"}
    office_row = create_item(db, "office_file", payload, case_id=case.id, parent_id=document_id, version=version,
                             item_id=f"{document_id}:v{version}", status="needs_review")
    # File edits with no registered business mapping must be visible as requiring reconciliation.
    create_item(db, "file_change", {"documentId": document_id, "version": version, "source": source,
        "status": "mapped" if mapping_result.get("coverageComplete") else "needs_review",
        "impactCoverage": "complete" if mapping_result.get("coverageComplete") else "incomplete", "actor": actor, "createdAt": now()}, case_id=case.id)
    if version > 1 and not mapping_result.get("coverageComplete"):
        db.flush()
        from .propagation import artifact_changed
        previous = _row(db, case, document_id, version - 1)
        previous_value = decode(previous.payload)
        kind = "working_file_" + document_id
        group = artifact_changed(db, case,
            {"itemId": previous.id, "kind": kind, "version": previous.version,
             "content": {"sha256": previous_value["sha256"], "source": source}},
            {"itemId": office_row.id, "kind": kind, "version": version,
             "content": {"sha256": blob.sha256, "source": source}})
        if group:
            payload["consistencyId"] = group["id"]
            payload["impactCoverage"] = "review_required"
            current_payload = decode(office_row.payload)
            office_row.payload = encode({**current_payload, "consistencyId": group["id"]})
    return payload


def _pdf(data, fmt):
    """Content preview PDF from exactly the downloaded Office version, with no separate data model."""
    from html import escape
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    style = ParagraphStyle("OfficeContent", fontName="STSong-Light", fontSize=10, leading=15)
    value = preview(data, fmt)
    blocks = [Paragraph("Content preview / 内容预览", style), Spacer(1, 12)]
    para = lambda text: Paragraph(escape(str(text if text is not None else "")).replace("\n", "<br/>"), style)
    if fmt == "docx":
        blocks.extend(para(item["text"]) for item in value["paragraphs"])
        for table in value["tables"]:
            if table["rows"]:
                item = Table([[para(cell) for cell in row] for row in table["rows"]])
                item.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .3, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
                blocks.extend([Spacer(1, 10), item])
        for image in value["images"]:
            decoded = base64.b64decode(image["url"].split(",", 1)[1])
            picture = Image(BytesIO(decoded))
            scale = min(1, 400 / picture.imageWidth, 500 / picture.imageHeight)
            picture.drawWidth, picture.drawHeight = picture.imageWidth * scale, picture.imageHeight * scale
            blocks.extend([Spacer(1, 10), picture])
    else:
        for sheet in value["sheets"]:
            blocks.extend([Spacer(1, 10), para(sheet["name"])])
            for row in sheet["rows"]:
                blocks.append(para(" | ".join(f"{cell['address']}: {cell['display']}" for cell in row if cell["display"] is not None)))
    buffer = BytesIO()
    SimpleDocTemplate(buffer, title="Office content preview").build(blocks)
    return buffer.getvalue()


def office_routes(request, db, user, case, tail, body, form):
    method = request.method
    if not tail and method == "GET":
        sources = []
        for kind in ("evidence", "agent_file", "export"):
            for row in items(db, kind, case_id=case.id):
                value = decode(row.payload)
                blob = db.get(Blob, value.get("blobId") or (value.get("ref") or {}).get("file_id"))
                if blob and blob.case_id == case.id and Path(blob.filename).suffix.lower()[1:] in FORMATS:
                    sources.append({"fileId": row.id, "name": blob.filename, "sha256": blob.sha256})
        latest = {}
        for row in items(db, "office_file", case_id=case.id):
            if row.parent_id not in latest or row.version > latest[row.parent_id].version:
                latest[row.parent_id] = row
        images = [{"fileId": row.id, "name": decode(row.payload).get("title", row.id)}
                  for row in [*items(db, "evidence", case_id=case.id), *items(db, "export", case_id=case.id)]
                  if (blob := db.get(Blob, decode(row.payload).get("blobId"))) and blob.media_type in ("image/png", "image/jpeg")]
        return {"sources": sources, "documents": [item_view(row) for row in latest.values()], "images": images}
    if method in ("POST", "PUT"):
        # Serialize the revision check and immutable version insert.
        db.rollback()
        db.execute(text("BEGIN IMMEDIATE"))
        db.refresh(case)
        if case.active_run_id or decode(case.payload).get("pendingRunId"):
            fail("RUN_IN_PROGRESS", "请等待当前 Agent 任务完成后编辑文件", 409)
    try:
        if not tail and method == "POST":
            source_row, blob, data = _source(db, case, body.get("fileId"))
            fmt = Path(blob.filename).suffix.lower()[1:]
            data = _normalize(data, fmt)
            preview(data, fmt)
            source = {"fileId": body["fileId"], "blobId": blob.id, "sha256": blob.sha256}
            mapping = _freeze_mapping(db, case, source_row, data, fmt)
            if mapping:
                source["templateMapping"] = mapping
            result = _save(db, case, uid("office"), source,
                           data, blob.filename, fmt, 1, user.id)
            db.commit()
            return result
        if not tail:
            fail("NOT_FOUND", "接口不存在", 404)
        document_id = tail[0]
        version = int(tail[2]) if len(tail) >= 3 and tail[1] == "versions" else None
        row = _row(db, case, document_id, version)
        value = decode(row.payload)
        blob, data = _bytes(db, case, value["blobId"])
        if method == "GET":
            if tail[-1] == "download":
                return FileResponse(blob.path, media_type=blob.media_type, filename=blob.filename)
            if tail[-1] == "pdf":
                return Response(_pdf(data, value["format"]), media_type="application/pdf",
                                headers={"Content-Disposition": f'attachment; filename="office-{document_id}-v{row.version}.pdf"'})
            return {**value, "preview": preview(data, value["format"]),
                    "versions": [item_view(r) for r in items(db, "office_file", case_id=case.id, parent_id=document_id)]}
        if len(tail) == 1 and method == "PUT":
            if body.get("baseVersion") != row.version or body.get("baseHash") != blob.sha256:
                fail("ARTIFACT_CONFLICT", "文件已更新，请重新加载当前版本", 409)
            updated = apply_edits(db, case, data, value["format"], body.get("operations"))
            preview(updated, value["format"])
            result = _save(db, case, document_id, value["source"], updated, value["name"], value["format"],
                           row.version + 1, user.id, body["operations"])
            db.commit()
            return result
    except (ValueError, KeyError, IndexError, TypeError, OverflowError, BadZipFile) as exc:
        fail("OFFICE_EDIT_UNSUPPORTED", str(exc)[:300], 422)
    fail("NOT_FOUND", "接口不存在", 404)
