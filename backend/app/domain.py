"""Deterministic domain rules for the bag export workbench.

The agent may read and propose values, but all money, completeness and gate
decisions are computed here from structured data. No DB or model imports.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any, Iterable


STAGES: tuple[dict[str, str], ...] = (
    {"key": "inquiry", "title": "客户与询盘", "short": "询盘"},
    {"key": "requirements", "title": "需求与规格", "short": "规格"},
    {"key": "costing", "title": "成本与报价", "short": "报价"},
    {"key": "sample", "title": "打样确认", "short": "打样"},
    {"key": "order", "title": "订单与合同", "short": "订单"},
    {"key": "production", "title": "生产准备", "short": "生产"},
    {"key": "shipment", "title": "出口出运", "short": "出运"},
    {"key": "payment", "title": "收款与售后", "short": "收款"},
)

STAGE_KEYS = tuple(stage["key"] for stage in STAGES)

# Ordered Tech Pack fields. `required` drives readiness, not whether a draft
# may be saved: unknown values must stay observable instead of being invented.
SPEC_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "key": "product",
        "title": "款式与结构",
        "fields": (
            {"key": "product", "label": "产品", "required": True},
            {"key": "quantity", "label": "数量", "required": True},
            {"key": "style", "label": "款式/使用场景"},
            {"key": "dimensions", "label": "尺寸", "required": True},
            {"key": "color", "label": "颜色"},
            {"key": "structure", "label": "内袋/隔层/口袋"},
            {"key": "laptopSleeve", "label": "电脑隔层"},
            {"key": "straps", "label": "肩带/提手"},
        ),
    },
    {
        "key": "material",
        "title": "材料",
        "fields": (
            {"key": "fabric", "label": "面料/克重", "required": True},
            {"key": "lining", "label": "里布"},
            {"key": "filling", "label": "填充/护板"},
            {"key": "materialFinish", "label": "涂层/防水"},
        ),
    },
    {
        "key": "accessory",
        "title": "辅料与标识",
        "fields": (
            {"key": "zipper", "label": "拉链/拉头"},
            {"key": "buckle", "label": "扣具/五金"},
            {"key": "webbing", "label": "织带"},
            {"key": "logo", "label": "LOGO 工艺/位置/尺寸", "required": True},
            {"key": "label", "label": "织唛/吊牌"},
        ),
    },
    {
        "key": "packaging",
        "title": "包装与装箱",
        "fields": (
            {"key": "packaging", "label": "内包装", "required": True},
            {"key": "cartonQty", "label": "装箱数量"},
            {"key": "cartonSize", "label": "外箱尺寸"},
            {"key": "cartonWeight", "label": "外箱重量"},
            {"key": "shippingMarks", "label": "唛头/条码"},
        ),
    },
    {
        "key": "quality",
        "title": "测试与验货",
        "fields": (
            {"key": "tests", "label": "测试/认证"},
            {"key": "inspection", "label": "验货标准", "required": True},
            {"key": "sampleRequirement", "label": "样品要求"},
        ),
    },
    {
        "key": "terms",
        "title": "贸易与交付",
        "fields": (
            {"key": "destination", "label": "目的地", "required": True},
            {"key": "incoterm", "label": "贸易术语", "required": True},
            {"key": "incotermsVersion", "label": "术语版本", "required": True},
            {"key": "namedPlace", "label": "指定地点/港口", "required": True},
            {"key": "paymentTerms", "label": "付款方式"},
            {"key": "delivery", "label": "交货要求"},
        ),
    },
)

SPEC_FIELDS: tuple[dict[str, Any], ...] = tuple(
    {**field, "group": group["key"]}
    for group in SPEC_GROUPS
    for field in group["fields"]
)
SPEC_KEYS = tuple(field["key"] for field in SPEC_FIELDS)
REQUIRED_SPEC_KEYS = tuple(field["key"] for field in SPEC_FIELDS if field.get("required"))

COST_CATEGORIES: tuple[dict[str, str], ...] = (
    {"key": "material", "label": "面料/材料"},
    {"key": "accessory", "label": "辅料/五金"},
    {"key": "labor", "label": "加工/缝制"},
    {"key": "packaging", "label": "包装"},
    {"key": "inspection", "label": "检验"},
    {"key": "domesticFreight", "label": "国内运输"},
    {"key": "exportCharges", "label": "出口费用"},
    {"key": "tooling", "label": "打样/版费摊销"},
    {"key": "overhead", "label": "管理/其他"},
)
COST_CATEGORY_KEYS = tuple(item["key"] for item in COST_CATEGORIES)

QUOTE_REQUIRED_FIELDS = (
    "product",
    "quantity",
    "unitPriceUsd",
    "incoterm",
    "incotermsVersion",
    "namedPlace",
    "paymentTerms",
    "validUntil",
    "costVersionId",
)

SAMPLE_TYPES = ("development", "confirmation", "pre_production")
SAMPLE_CHECKS = ("appearance", "dimensions", "function", "workmanship", "packaging")


class DomainError(ValueError):
    """Raised when a value cannot be represented without inventing data."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DomainError("INVALID_TEXT", "字段必须是文本")
    value = value.strip()
    return value or None


def _number(value: Any, field: str = "value") -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise DomainError("INVALID_NUMBER", f"{field} 不是有效数字") from None
    if not number.is_finite():
        raise DomainError("INVALID_NUMBER", f"{field} 不是有效数字")
    return number


def empty_spec() -> dict:
    return {"fields": {key: None for key in SPEC_KEYS}, "missing": list(REQUIRED_SPEC_KEYS), "sourceRefs": []}


def normalize_spec(value: dict | None) -> dict:
    """Merge arbitrary partial input into the canonical spec shape.

    Unknown keys are rejected by callers before this helper; here we only keep
    the canonical field set and never invent a value.
    """
    if value is None:
        return empty_spec()
    if not isinstance(value, dict):
        raise DomainError("INVALID_SPEC", "规格必须是对象")
    fields = value.get("fields") if isinstance(value.get("fields"), dict) else value
    result = empty_spec()
    for key in SPEC_KEYS:
        if key in fields:
            result["fields"][key] = _text(fields[key])
    result["missing"] = missing_spec_fields(result["fields"])
    result["sourceRefs"] = value.get("sourceRefs") if isinstance(value.get("sourceRefs"), list) else []
    return result


def merge_spec(current: dict | None, patch: dict | None) -> dict:
    if patch is not None and not isinstance(patch, dict):
        raise DomainError("INVALID_SPEC", "规格更新必须是对象")
    base = normalize_spec(current)
    if patch:
        patch_fields = patch.get("fields") if isinstance(patch.get("fields"), dict) else patch
        unknown = [key for key in patch_fields if key not in SPEC_KEYS]
        if unknown:
            raise DomainError("UNKNOWN_SPEC_FIELD", f"未知规格字段：{', '.join(unknown[:8])}")
        for key in SPEC_KEYS:
            if key in patch_fields:
                base["fields"][key] = _text(patch_fields[key])
        if isinstance(patch.get("sourceRefs"), list):
            base["sourceRefs"] = patch["sourceRefs"]
    base["missing"] = missing_spec_fields(base["fields"])
    return base


def missing_spec_fields(fields: dict | None) -> list[str]:
    fields = fields or {}
    return [key for key in REQUIRED_SPEC_KEYS if not fields.get(key)]


def spec_ready(spec: dict | None) -> bool:
    if not spec:
        return False
    return not missing_spec_fields(spec.get("fields"))


def normalize_bom(rows: Iterable[dict] | None) -> list[dict]:
    result = []
    for raw in rows or []:
        if not isinstance(raw, dict):
            raise DomainError("INVALID_BOM", "BOM 行必须是对象")
        item = _text(raw.get("item"))
        if not item:
            raise DomainError("INVALID_BOM", "BOM 行缺少物料名称")
        result.append(
            {
                "category": _text(raw.get("category")) or "material",
                "item": item,
                "spec": _text(raw.get("spec")),
                "quantityPerPiece": _text(raw.get("quantityPerPiece")),
                "unit": _text(raw.get("unit")),
                "supplier": _text(raw.get("supplier")),
                "unitPriceCny": _text(raw.get("unitPriceCny")),
                "wastage": _text(raw.get("wastage")),
                "sourceId": _text(raw.get("sourceId")),
            }
        )
    return result


def calculate_cost(lines: Iterable[dict] | None, *, exchange_rate: Any, margin: Any, quantity: Any) -> dict:
    """Return the canonical cost result or raise DomainError.

    Formula: unit_price_usd = ceil_cent((sum(per_unit_lines) / fx) / (1 - margin)).
    Quantity is a positive integer; margin is a ratio in [0, 1).
    """
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1 or quantity > 100_000_000:
        raise DomainError("INVALID_QUANTITY", "数量必须是正整数")
    fx = _number(exchange_rate, "汇率")
    ratio = _number(margin, "毛利率")
    if fx <= 0:
        raise DomainError("INVALID_FX", "汇率必须大于 0")
    if ratio < 0 or ratio >= 1:
        raise DomainError("INVALID_MARGIN", "毛利率必须在 0 到 1 之间")
    normalized = []
    total = Decimal("0")
    for raw in lines or []:
        if not isinstance(raw, dict):
            raise DomainError("INVALID_COST_LINE", "成本行必须是对象")
        category = _text(raw.get("category")) or "overhead"
        if category not in COST_CATEGORY_KEYS:
            raise DomainError("UNKNOWN_COST_CATEGORY", f"未知成本类别：{category}")
        amount = _number(raw.get("amountCny"), "成本金额")
        if amount < 0:
            raise DomainError("INVALID_COST_LINE", "成本金额不能为负")
        scope = raw.get("scope") or "per_unit"
        if scope not in ("per_unit", "per_order"):
            raise DomainError("INVALID_COST_SCOPE", "成本范围只支持 per_unit 或 per_order")
        per_unit = amount if scope == "per_unit" else amount / Decimal(quantity)
        total += per_unit
        normalized.append(
            {
                "category": category,
                "label": _text(raw.get("label")) or category,
                "amountCny": str(amount),
                "scope": scope,
                "perUnitCny": str(per_unit.quantize(Decimal("0.0001"))),
                "sourceId": _text(raw.get("sourceId")),
            }
        )
    if not normalized:
        raise DomainError("MISSING_COST", "至少需要一条成本行")
    unit = (total / fx / (Decimal(1) - ratio)).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    return {
        "lines": normalized,
        "unitCostCny": str(total.quantize(Decimal("0.01"))),
        "exchangeRate": str(fx),
        "margin": str(ratio),
        "quantity": quantity,
        "unitPriceUsd": str(unit),
        "totalUsd": str(unit * quantity),
        "formula": "ceil_cent((sum(per_unit_cost) / fx) / (1 - margin))",
    }


def missing_quote_fields(quotation: dict | None) -> list[str]:
    quotation = quotation or {}
    missing = []
    for key in QUOTE_REQUIRED_FIELDS:
        value = quotation.get(key)
        if value is None or value == "":
            missing.append(key)
    if quotation.get("incotermsVersion") and quotation.get("incotermsVersion") != "2020":
        missing.append("incotermsVersion")
    if quotation.get("validUntil") and not _valid_date(str(quotation["validUntil"])):
        missing.append("validUntil")
    if quotation.get("validUntil") and _valid_date(str(quotation["validUntil"])):
        from datetime import date
        try:
            if date.fromisoformat(str(quotation["validUntil"])) < date.today():
                missing.append("expired")
        except ValueError:
            missing.append("validUntil")
    return missing


def _valid_date(value: str) -> bool:
    from datetime import date
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def quote_total(quotation: dict | None) -> Decimal | None:
    quotation = quotation or {}
    unit = quotation.get("unitPriceUsd")
    quantity = quotation.get("quantity")
    if unit is None or quantity is None:
        return None
    try:
        return _number(unit, "单价") * Decimal(int(quantity))
    except (DomainError, ValueError, TypeError):
        return None


def order_diff(order: dict | None, quotation: dict | None, spec: dict | None) -> list[dict]:
    order = order or {}
    po = order.get("po") or {}
    quotation = quotation or {}
    spec = spec or {}
    fields = (
        ("quantity", po.get("quantity"), quotation.get("quantity")),
        ("unitPriceUsd", po.get("unitPriceUsd"), quotation.get("unitPriceUsd")),
        ("incoterm", po.get("incoterm"), quotation.get("incoterm")),
        ("namedPlace", po.get("namedPlace"), quotation.get("namedPlace")),
        ("paymentTerms", po.get("paymentTerms"), quotation.get("paymentTerms")),
        ("destination", po.get("destination"), spec.get("fields", {}).get("destination")),
        ("deliveryDate", po.get("deliveryDate"), spec.get("fields", {}).get("delivery")),
    )
    result = []
    for field, actual, baseline in fields:
        if actual in (None, "") and baseline in (None, ""):
            continue
        if actual in (None, ""):
            status = "missing"
        elif baseline in (None, ""):
            status = "review"
        elif str(actual) == str(baseline):
            status = "match"
        elif field in ("paymentTerms", "deliveryDate"):
            # Free-text clauses are rarely worded identically across PO and
            # quotation. Flag them for human review instead of a hard conflict.
            status = "review"
        else:
            status = "conflict"
        result.append({"field": field, "po": actual, "baseline": baseline, "status": status})
    return result


def can_generate_node(node: str, latest: dict[str, dict] | None) -> bool:
    """Downstream nodes only unlock after their prerequisite exists."""
    latest = latest or {}
    requirements = ("spec", "bom")
    if node == "inquiry":
        return True
    if node == "requirements":
        return True
    if node == "costing":
        return "spec" in latest
    if node == "sample":
        return "spec" in latest and "quotation" in latest
    if node == "order":
        return "quotation" in latest and "sample" in latest
    if node == "production":
        return "order" in latest
    return False


def payment_schedule_errors(schedule: Any, order_total: Any = None) -> list[str]:
    """Validate a human-facing payment schedule without inventing dates."""
    if not isinstance(schedule, list) or not schedule:
        return ["付款计划为空"]
    errors: list[str] = []
    total = None
    if order_total not in (None, ""):
        try:
            total = _number(order_total, "订单总额")
        except DomainError:
            errors.append("订单总额无效")
    ratio_sum = Decimal("0")
    for index, row in enumerate(schedule, 1):
        if not isinstance(row, dict):
            errors.append(f"第 {index} 个付款节点格式无效")
            continue
        if not _text(row.get("milestone")):
            errors.append(f"第 {index} 个付款节点缺少名称")
        if not _text(row.get("due")):
            errors.append(f"第 {index} 个付款节点缺少到期/触发条件")
        try:
            ratio = _number(row.get("ratio"), "付款比例")
            amount = _number(row.get("amountUsd"), "付款金额")
        except DomainError:
            errors.append(f"第 {index} 个付款节点比例或金额无效")
            continue
        if ratio <= 0 or ratio > 1:
            errors.append(f"第 {index} 个付款节点比例必须在 0-1 之间")
        if amount <= 0:
            errors.append(f"第 {index} 个付款节点金额必须大于 0")
        ratio_sum += ratio
        if total is not None and abs(amount - ratio * total) > Decimal("0.01"):
            errors.append(f"第 {index} 个付款节点金额与比例×订单总额不一致")
    if ratio_sum > Decimal("1.001"):
        errors.append("付款比例合计超过 100%")
    return errors
