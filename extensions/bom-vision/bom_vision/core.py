from __future__ import annotations

import copy
import hashlib
import io
import json
import re
import warnings
from decimal import Decimal, localcontext
from typing import Any, Mapping

from PIL import Image

from .adapters import VisionAdapter

FIELDS = ("material_name", "specification", "quantity", "unit", "unit_price", "currency", "subtotal")
MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 25_000_000
# Conservative list: unfamiliar units are kept and questioned, never converted.
UNITS = {"m", "m2", "m²", "cm", "mm", "kg", "g", "pcs", "pc", "piece", "pieces",
         "set", "sets", "pair", "pairs", "yd", "yard", "yards", "米", "厘米", "毫米",
         "平方米", "码", "克", "千克", "公斤", "个", "件", "套", "对", "条", "只"}


class InputError(ValueError):
    pass


def inspect_image(image: bytes) -> dict:
    if not image or len(image) > MAX_BYTES:
        raise InputError("image_size_invalid")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(image)) as im:
                if im.format not in {"PNG", "JPEG"}:
                    raise InputError("unsupported_image_type")
                if im.width * im.height > MAX_PIXELS or getattr(im, "n_frames", 1) != 1:
                    raise InputError("image_dimensions_invalid")
                info = {"mime_type": Image.MIME[im.format], "width": im.width, "height": im.height}
                im.verify()
            with Image.open(io.BytesIO(image)) as im:
                im.load()  # verify alone does not catch every truncated JPEG.
        return info
    except InputError:
        raise
    except Exception:
        raise InputError("image_decode_failed") from None


def _string(value: Any, label: str, nullable: bool = True) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or len(value) > 100_000:
        raise InputError(f"invalid_{label}")
    return value if value.strip() else (None if nullable else "")


def _strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or len(value) > 1000:
        raise InputError(f"invalid_{label}")
    return [_string(item, label, False) for item in value]


def parse_response(raw: str) -> dict:
    if not isinstance(raw, str) or len(raw) > 1_000_000:
        raise InputError("invalid_model_response")
    text = raw.strip()
    if text.startswith("```json\n") and text.endswith("```"):
        text = text[8:-3]
    elif text.startswith("```\n") and text.endswith("```"):
        text = text[4:-3]
    try:
        value = json.loads(text)
    except ValueError:
        raise InputError("model_response_not_json") from None
    if not isinstance(value, dict) or set(value) != {"raw_text", "rows", "table_total", "currency", "notes"}:
        raise InputError("model_response_schema_invalid")
    rows = value["rows"]
    if not isinstance(rows, list) or len(rows) > 500:
        raise InputError("invalid_rows")
    result = {"raw_text": _string(value["raw_text"], "raw_text", False),
              "table_total": _string(value["table_total"], "table_total"),
              "currency": _string(value["currency"], "currency"),
              "notes": _strings(value["notes"], "notes"), "rows": []}
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or set(row) != set(FIELDS) | {"raw_text", "source_line", "uncertain_fields"}:
            raise InputError("invalid_row_schema")
        line = row["source_line"]
        if type(line) is not int or line < 1:
            raise InputError("invalid_source_line")
        uncertain = _strings(row["uncertain_fields"], "uncertain_fields")
        if not set(uncertain) <= set(FIELDS):
            raise InputError("invalid_uncertain_fields")
        raw_text = _string(row["raw_text"], "row_raw_text", False)
        if not raw_text:
            raise InputError("row_source_text_required")
        candidate = {field: _string(row[field], field) for field in FIELDS}
        candidate.update(id=f"row-{index}", uncertain_fields=uncertain,
                         source={"kind": "visual_row_text", "line": line, "raw_text": raw_text},
                         corrected_fields=[])
        result["rows"].append(candidate)
    return result


def recognize(image: bytes, file_ref: Mapping, adapter: VisionAdapter) -> dict:
    """Caller supplies an already-authorized immutable FileRef; no disk/network lookup here."""
    if not isinstance(file_ref, Mapping) or not file_ref:
        raise InputError("file_ref_required")
    info = inspect_image(image)
    raw = adapter.extract(image, info["mime_type"])
    result = parse_response(raw)
    result.update(schema_version="bom-vision-candidate-v1", status="candidate", revision=1,
                  source={"file_ref": copy.deepcopy(dict(file_ref)),
                          "sha256": hashlib.sha256(image).hexdigest(), **info},
                  recognition={"adapter": adapter.name, "raw_response": raw,
                               "original_extraction": copy.deepcopy(result)},
                  corrections=[])
    return revalidate(result)


def _number(value: Any) -> Decimal | None:
    # Avoid locale guessing, grouping removal, exponent/nonfinite values and huge arithmetic.
    if not isinstance(value, str) or not re.fullmatch(r"[+-]?\d{1,15}(?:\.\d{1,8})?", value.strip(), re.ASCII):
        return None
    return Decimal(value.strip())


def revalidate(candidate: dict) -> dict:
    """Pure revalidation; never fills missing prices, approves or converts units/currencies."""
    result = copy.deepcopy(candidate)
    if result.get("schema_version") != "bom-vision-candidate-v1":
        raise InputError("unsupported_candidate_schema")
    if not isinstance(result.get("rows"), list) or len(result["rows"]) > 500:
        raise InputError("invalid_candidate_rows")
    issues = []

    def issue(code, message, row_id=None, field=None):
        issues.append({"code": code, "row_id": row_id, "field": field, "question": message})

    sums: dict[str, Decimal] = {}
    complete = True
    seen = set()
    for row in result["rows"]:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or row["id"] in seen:
            raise InputError("invalid_candidate_row_id")
        seen.add(row["id"])
        rid = row["id"]
        uncertain = _strings(row.get("uncertain_fields"), "uncertain_fields")
        if not set(uncertain) <= set(FIELDS):
            raise InputError("invalid_uncertain_fields")
        for field in FIELDS:
            val = _string(row.get(field), field)
            if val is None:
                issue("missing_field", "原表是否包含此字段？请核对原图后补充。", rid, field)
            if field in uncertain:
                issue("uncertain_value", "识别不确定，请核对数字、小数点或文字。", rid, field)
        nums = {}
        for field in ("quantity", "unit_price", "subtotal"):
            value = row.get(field)
            n = _number(value)
            if value is not None and n is None:
                issue("decimal_ambiguous", "数字格式不明确；请确认小数点/千位分隔符，使用十进制数字。", rid, field)
            if n is not None and n < 0:
                issue("negative_value", "发现负数，请核对是否为退料或识别错误。", rid, field)
            nums[field] = n if field not in uncertain else None
        unit = row.get("unit")
        if unit and unit.strip().lower() not in UNITS:
            issue("unit_unrecognized", "单位未识别或包含换算/计价基数，请核对；不会自动换算。", rid, "unit")
        q, p, subtotal = (nums[f] for f in ("quantity", "unit_price", "subtotal"))
        if all(n is not None for n in (q, p, subtotal)):
            with localcontext() as ctx:
                ctx.prec = 64
                product = q * p
                if abs(product - subtotal) > Decimal("0.01"):
                    issue("row_amount_mismatch", f"用量×单价={product}，原行小计={subtotal}；请核对小数点及计价单位。", rid, "subtotal")
        currency = row.get("currency")
        if currency is not None and not re.fullmatch(r"[A-Z]{3}", currency, re.ASCII):
            issue("currency_ambiguous", "请核对币种并使用 ISO 三字母代码；货币符号可能不唯一。", rid, "currency")
        if subtotal is None or not currency or "currency" in uncertain or not re.fullmatch(r"[A-Z]{3}", currency, re.ASCII):
            complete = False
        else:
            with localcontext() as ctx:
                ctx.prec = 64
                sums[currency] = sums.get(currency, Decimal(0)) + subtotal
    if not result["rows"]:
        issue("no_rows", "没有可识别候选行，请提供清晰完整的表格图片。")
        complete = False
    total = _string(result.get("table_total"), "table_total")
    total_currency = _string(result.get("currency"), "currency")
    if total is None:
        issue("missing_table_total", "原表合计缺失或不清晰，请核对。", field="table_total")
    elif _number(total) is None:
        issue("decimal_ambiguous", "原表合计小数点/数字格式不明确，请核对。", field="table_total")
    elif _number(total) < 0:
        issue("negative_value", "原表合计为负数，请核对。", field="table_total")
    if not total_currency or not re.fullmatch(r"[A-Z]{3}", total_currency, re.ASCII):
        issue("currency_ambiguous", "原表合计币种缺失或不明确。", field="currency")
    comparable = complete and len(sums) == 1 and total_currency in sums and _number(total) is not None
    if len(sums) > 1:
        issue("mixed_currencies", "候选行包含多个币种，不进行跨币种求和。")
    if not comparable:
        issue("total_not_comparable", "缺少可比较的同币种完整行小计或表合计；不能确认合计一致。")
    elif abs(sums[total_currency] - _number(total)) > Decimal("0.01"):
        issue("table_total_mismatch", f"原行小计之和={sums[total_currency]}，原表合计={total}；请核对遗漏、税费及数字。", field="table_total")
    notes = _strings(result.get("notes"), "notes")
    for note in notes:
        issue("recognition_note", note)
    result.update(status="candidate", issues=issues,
                  validation={"needs_review": True, "has_questions": bool(issues),
                              "subtotal_sums_by_currency": {k: str(v) for k, v in sums.items()},
                              "total_comparable": comparable,
                              "amount_tolerance": "0.01", "price_approved": False})
    return result


def correct(candidate: dict, patches: list[dict], *, expected_revision: int, actor: str, reason: str) -> dict:
    """Apply atomic candidate edits with optimistic revision checking and retained source evidence."""
    result = revalidate(candidate)
    revision = result.get("revision")
    if type(expected_revision) is not int or revision != expected_revision:
        raise InputError("candidate_revision_conflict")
    if not isinstance(actor, str) or not actor.strip() or not isinstance(reason, str) or not reason.strip():
        raise InputError("correction_actor_and_reason_required")
    if not isinstance(patches, list) or not 1 <= len(patches) <= 1000:
        raise InputError("invalid_patches")
    rows = {row["id"]: row for row in result["rows"]}
    touched = set()
    for patch in patches:
        if not isinstance(patch, dict) or set(patch) != {"row_id", "field", "value"}:
            raise InputError("invalid_patch")
        rid, field = patch["row_id"], patch["field"]
        if not (isinstance(rid, str) or rid is None) or not isinstance(field, str):
            raise InputError("invalid_patch_target")
        if (rid, field) in touched:
            raise InputError("duplicate_patch")
        touched.add((rid, field))
        if rid is None and field in {"table_total", "currency"}:
            target = result
        elif rid in rows and field in FIELDS:
            target = rows[rid]
        else:
            raise InputError("invalid_patch_target")
        value = _string(patch["value"], field)
        result["corrections"].append({"revision": revision + 1, "actor": actor, "reason": reason,
                                      "row_id": rid, "field": field, "before": target.get(field), "after": value})
        target[field] = value
        if rid is not None:
            target["uncertain_fields"] = [f for f in target["uncertain_fields"] if f != field]
            target["corrected_fields"] = sorted(set(target["corrected_fields"]) | {field})
    result["revision"] = revision + 1
    return revalidate(result)
