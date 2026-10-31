from decimal import Decimal

import pytest

from app.domain import (
    DomainError,
    calculate_cost,
    can_generate_node,
    merge_spec,
    missing_quote_fields,
    missing_spec_fields,
    normalize_bom,
    order_diff,
    spec_ready,
)


def test_cost_formula_reproduces_golden_quote():
    cost = calculate_cost(
        [
            {"category": "material", "label": "fabric", "amountCny": "44"},
            {"category": "packaging", "label": "box", "amountCny": "2"},
            {"category": "domesticFreight", "label": "local", "amountCny": "4"},
        ],
        exchange_rate="7.20",
        margin="0.20",
        quantity=3000,
    )
    assert cost["unitCostCny"] == "50.00"
    assert cost["unitPriceUsd"] == "8.69"
    assert cost["totalUsd"] == "26070.00"


def test_cost_formula_color_box_change():
    cost = calculate_cost(
        [
            {"category": "material", "label": "fabric", "amountCny": "44"},
            {"category": "packaging", "label": "color box", "amountCny": "5"},
            {"category": "domesticFreight", "label": "local", "amountCny": "4"},
        ],
        exchange_rate="7.2",
        margin="0.2",
        quantity=3000,
    )
    assert cost["unitPriceUsd"] == "9.21"
    assert cost["totalUsd"] == "27630.00"


def test_per_order_lines_are_amortized():
    cost = calculate_cost(
        [
            {"category": "material", "label": "fabric", "amountCny": "80"},
            {"category": "tooling", "label": "mold", "amountCny": "600", "scope": "per_order"},
        ],
        exchange_rate="7.2",
        margin="0.1",
        quantity=300,
    )
    assert Decimal(cost["unitCostCny"]) == Decimal("82.00")
    assert cost["unitPriceUsd"] == "12.66"


@pytest.mark.parametrize("margin", ["1", "1.2", "-0.1"])
def test_margin_must_be_ratio(margin):
    with pytest.raises(DomainError):
        calculate_cost([{"category": "material", "amountCny": "1"}], exchange_rate="7.2", margin=margin, quantity=1)


def test_spec_merge_keeps_unknown_and_tracks_required():
    spec = merge_spec(None, {"product": "backpack", "quantity": "3000", "dimensions": "30x45"})
    assert spec["fields"]["product"] == "backpack"
    assert spec["fields"]["fabric"] is None
    assert not spec_ready(spec)
    assert "fabric" in spec["missing"]
    spec = merge_spec(spec, {"fabric": "600D", "logo": "embroidery", "packaging": "polybag", "inspection": "AQL 2.5", "destination": "Hamburg", "incoterm": "FOB", "incotermsVersion": "2020", "namedPlace": "Ningbo"})
    assert spec_ready(spec)
    assert missing_spec_fields(spec["fields"]) == []


def test_unknown_spec_field_is_rejected():
    with pytest.raises(DomainError):
        merge_spec(None, {"invented": "x"})


def test_bom_requires_item():
    with pytest.raises(DomainError):
        normalize_bom([{"spec": "x"}])
    assert normalize_bom([{"item": "zipper", "spec": "YKK #5"}])[0]["category"] == "material"


def test_quote_requires_trade_terms_and_valid_date():
    quote = {"product": "backpack", "quantity": 1, "unitPriceUsd": "1.00", "incoterm": "FOB", "incotermsVersion": "2020", "namedPlace": "Ningbo", "paymentTerms": "T/T", "validUntil": "2999-01-01", "costVersionId": "cost_v1"}
    assert missing_quote_fields(quote) == []
    assert "incotermsVersion" in missing_quote_fields({**quote, "incotermsVersion": "2010"})
    assert "validUntil" in missing_quote_fields({**quote, "validUntil": "not-a-date"})


def test_order_diff_flags_price_and_quantity():
    diff = order_diff(
        {"po": {"quantity": 3000, "unitPriceUsd": "9.21", "incoterm": "FOB", "namedPlace": "Ningbo"}},
        {"quantity": 3000, "unitPriceUsd": "9.21", "incoterm": "FOB", "namedPlace": "Ningbo"},
        {"fields": {"destination": "Hamburg"}},
    )
    assert [row for row in diff if row["status"] == "conflict"] == []
    diff = order_diff({"po": {"quantity": 2900, "unitPriceUsd": "9.00"}}, {"quantity": 3000, "unitPriceUsd": "9.21"}, {"fields": {}})
    assert {row["field"] for row in diff if row["status"] == "conflict"} >= {"quantity", "unitPriceUsd"}


def test_node_dependencies():
    assert can_generate_node("requirements", {})
    assert not can_generate_node("costing", {})
    assert can_generate_node("costing", {"spec": {}})
    assert not can_generate_node("order", {"spec": {}, "quotation": {}})
