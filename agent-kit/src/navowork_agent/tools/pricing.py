from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_CEILING, localcontext
from typing import Literal
from pydantic import Field, StrictInt
from navowork_agent.contracts import Model, Fact, Question, AgentError


def number(value) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError("A finite decimal value is required")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal") from exc
    if not result.is_finite() or abs(result) > Decimal("1e18"):
        raise ValueError("Decimal is nonfinite or exceeds supported range")
    return result


class CostLine(Model):
    category: str = Field(min_length=1)
    amount: Fact
    scope: Literal["per_unit", "per_order"]
    currency: Literal["CNY"] = "CNY"


class PricingInput(Model):
    quantity: StrictInt = Field(gt=0, le=1_000_000_000)
    costs: list[CostLine] = Field(min_length=1, max_length=100)
    fx_cny_per_usd: Fact
    target_gross_margin: Fact
    moq: Fact = Field(default_factory=lambda: Fact(value=None))


class ContentSnapshot(Model):
    fields: dict[str, Fact]
    pricing: PricingInput | None = None
    internal_notes: dict[str, str] = Field(default_factory=dict)
    supplier: str | None = None


def calculate_quote(inputs: PricingInput) -> dict:
    """One Decimal implementation; no filesystem names or case-specific prices."""
    names = [c.category for c in inputs.costs]
    if len(names) != len(set(names)):
        raise ValueError("Cost categories must be unique")
    required = {"base", "packaging", "local"}
    missing = sorted(required - set(names))
    missing += ["costs." + c.category for c in inputs.costs if c.amount.value is None]
    if inputs.fx_cny_per_usd.value is None:
        missing.append("fx_cny_per_usd")
    if inputs.target_gross_margin.value is None:
        missing.append("target_gross_margin")
    if missing:
        return {"status": "needs_info", "missing": missing, "quote": None}
    fx = number(inputs.fx_cny_per_usd.value)
    margin = number(inputs.target_gross_margin.value)
    if fx <= 0 or not 0 <= margin < 1:
        raise ValueError("FX must be positive; gross margin is a ratio in [0, 1)")
    if inputs.moq.value is not None:
        moq = number(inputs.moq.value)
        if moq <= 0 or moq != moq.to_integral_value():
            raise ValueError("MOQ must be a positive integer")
        if inputs.quantity < moq:
            return {"status": "blocked", "missing": [], "quote": None, "reason": "QUANTITY_BELOW_MOQ"}
    with localcontext() as ctx:
        ctx.prec = 40
        unit_cost = Decimal(0)
        for cost in inputs.costs:
            amount = number(cost.amount.value)
            if amount < 0:
                raise ValueError("Cost cannot be negative")
            unit_cost += amount if cost.scope == "per_unit" else amount / inputs.quantity
        unit = (unit_cost / fx / (1 - margin)).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
        return {"status": "success", "missing": [], "quote": {
            "cost_cny_per_piece": str(unit_cost), "unit_usd": f"{unit:.2f}",
            "total_usd": f"{unit * inputs.quantity:.2f}", "quantity": inputs.quantity,
            "rounding": "unit ROUND_CEILING 0.01 USD, then multiply quantity", "rule_version": "quote-v1",
        }}


def missing_question(fields: list[str], affected=None) -> Question:
    from navowork_agent.contracts import digest
    return Question(question_id="q_" + digest(sorted(fields))[:16], missing_fields=fields,
                    affected_artifacts=affected or ["cost", "quotation"],
                    prompt="Please provide source evidence or an explicit user decision for: " + ", ".join(fields))
