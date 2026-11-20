"""Contribution profit and margin calculator (DATA_DICTIONARY.md §6, TEST_PLAN M1–M5).

Pure domain logic (zero I/O, zero Frappe DB dependency):
- Uses decimal.Decimal exclusively; never float for money.
- GST (`gst_rate`) is explicitly excluded: tax collected is a pass-through
  liability, never contribution profit or revenue (ARCHITECTURE_RULES.md §5).
- Formula:
    contribution_profit =
        selling_price
      - supplier_cost
      - shipping_cost
      - (packaging_cost or 0)
      - (selling_price * payment_fee_percent / 100)
      - (selling_price * expected_return_rate / 100 * return_cost_factor)
    contribution_margin_pct = contribution_profit / selling_price * 100
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

PAISA = Decimal("0.01")
HUNDRED = Decimal("100")


def _dec(value, name: str) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a valid decimal number") from exc
    if d.is_nan() or d.is_infinite():
        raise ValueError(f"{name} must be finite")
    return d


def quantize_money(amount: Decimal) -> Decimal:
    return amount.quantize(PAISA, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class MarginResult:
    selling_price: Decimal
    supplier_cost: Decimal
    shipping_cost: Decimal
    packaging_cost: Decimal
    payment_fee_amount: Decimal
    expected_return_cost: Decimal
    contribution_profit: Decimal
    contribution_margin_pct: Decimal
    can_publish: bool
    currency: str = "INR"


def calculate_contribution_profit(
    *,
    selling_price,
    supplier_cost,
    shipping_cost,
    packaging_cost=0,
    payment_fee_percent=0,
    expected_return_rate=0,
    return_cost_factor=1,
    gst_rate=0,
    currency: str = "INR",
) -> MarginResult:
    """Compute contribution profit and margin percent to exact paisa.

    Note: `gst_rate` is validated for range [0, 100] and intentionally excluded
    from contribution profit because GST is a pass-through tax liability.
    """
    sp = _dec(selling_price, "selling_price")
    sc = _dec(supplier_cost, "supplier_cost")
    ship = _dec(shipping_cost, "shipping_cost")
    pack = _dec(packaging_cost, "packaging_cost")
    fee_pct = _dec(payment_fee_percent, "payment_fee_percent")
    ret_pct = _dec(expected_return_rate, "expected_return_rate")
    ret_factor = _dec(return_cost_factor, "return_cost_factor")
    gst = _dec(gst_rate, "gst_rate")

    if sp <= Decimal("0"):
        raise ValueError("selling_price must be greater than zero")
    if sc < Decimal("0"):
        raise ValueError("supplier_cost cannot be negative")
    if ship < Decimal("0"):
        raise ValueError("shipping_cost cannot be negative")
    if pack < Decimal("0"):
        raise ValueError("packaging_cost cannot be negative")
    if not (Decimal("0") <= fee_pct <= HUNDRED):
        raise ValueError("payment_fee_percent must be between 0 and 100")
    if not (Decimal("0") <= ret_pct <= HUNDRED):
        raise ValueError("expected_return_rate must be between 0 and 100")
    if ret_factor < Decimal("0"):
        raise ValueError("return_cost_factor cannot be negative")
    if not (Decimal("0") <= gst <= HUNDRED):
        raise ValueError("gst_rate must be between 0 and 100")

    payment_fee_amount = quantize_money(sp * fee_pct / HUNDRED)
    expected_return_cost = quantize_money(sp * ret_pct / HUNDRED * ret_factor)

    profit = quantize_money(sp - sc - ship - pack - payment_fee_amount - expected_return_cost)
    margin_pct = quantize_money((profit / sp) * HUNDRED)

    return MarginResult(
        selling_price=quantize_money(sp),
        supplier_cost=quantize_money(sc),
        shipping_cost=quantize_money(ship),
        packaging_cost=quantize_money(pack),
        payment_fee_amount=payment_fee_amount,
        expected_return_cost=expected_return_cost,
        contribution_profit=profit,
        contribution_margin_pct=margin_pct,
        can_publish=profit >= Decimal("0.00"),
        currency=(currency or "INR").upper(),
    )


compute_margin = calculate_contribution_profit
