"""Supplier reliability and product opportunity scoring (DATA_DICTIONARY.md §7, TEST_PLAN M6–M7).

Pure domain logic (zero I/O):
- Supplier reliability score (clamped 0–100):
    score = 100
          - (cancellation_rate * 2.0)
          - (return_rate * 2.5)
          - (quality_issues / max(orders_fulfilled, 1) * 100 * 1.5)
          - dispatch_penalty
  where dispatch_penalty = 0 for avg_dispatch_hours <= 48, scaling linearly to 15 at 120 h.
- Product score (clamped 0–100):
  Weighted combination of margin, demand, competition, and supplier_reliability.
  When supplier_reliability is missing (None), computes from available factors
  normalized by their combined weights and sets `is_incomplete = True` (M7).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

ZERO = Decimal("0")
HUNDRED = Decimal("100")
QUANT = Decimal("0.01")


def _dec(value, name: str) -> Decimal:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a valid decimal number") from exc
    if d.is_nan() or d.is_infinite():
        raise ValueError(f"{name} must be finite")
    return d


def _clamp(value: Decimal, low: Decimal = ZERO, high: Decimal = HUNDRED) -> Decimal:
    return max(low, min(high, value))


@dataclass(frozen=True)
class ReliabilityResult:
    cancellation_rate: Decimal
    return_rate: Decimal
    dispatch_penalty: Decimal
    reliability_score: Decimal


def calculate_dispatch_penalty(avg_dispatch_hours) -> Decimal:
    if avg_dispatch_hours is None:
        return ZERO
    hours = _dec(avg_dispatch_hours, "avg_dispatch_hours")
    if hours < ZERO:
        raise ValueError("avg_dispatch_hours cannot be negative")
    if hours <= Decimal("48"):
        return ZERO
    if hours >= Decimal("120"):
        return Decimal("15.00")
    penalty = ((hours - Decimal("48")) / Decimal("72")) * Decimal("15")
    return penalty.quantize(QUANT, rounding=ROUND_HALF_UP)


def calculate_supplier_reliability(
    *,
    orders_received: int,
    orders_fulfilled: int,
    orders_cancelled: int,
    orders_returned: int,
    avg_dispatch_hours=None,
    quality_issues: int = 0,
) -> ReliabilityResult:
    if any(
        v < 0
        for v in (orders_received, orders_fulfilled, orders_cancelled, orders_returned, quality_issues)
    ):
        raise ValueError("Order counts and quality_issues cannot be negative")

    denom_received = Decimal(max(orders_received, 1))
    denom_fulfilled = Decimal(max(orders_fulfilled, 1))

    cancellation_rate = (Decimal(orders_cancelled) / denom_received * HUNDRED).quantize(
        QUANT, rounding=ROUND_HALF_UP
    )
    return_rate = (Decimal(orders_returned) / denom_fulfilled * HUNDRED).quantize(
        QUANT, rounding=ROUND_HALF_UP
    )
    quality_rate = Decimal(quality_issues) / denom_fulfilled * HUNDRED
    dispatch_penalty = calculate_dispatch_penalty(avg_dispatch_hours)

    raw_score = (
        HUNDRED
        - (cancellation_rate * Decimal("2.0"))
        - (return_rate * Decimal("2.5"))
        - (quality_rate * Decimal("1.5"))
        - dispatch_penalty
    )
    score = _clamp(raw_score).quantize(QUANT, rounding=ROUND_HALF_UP)

    return ReliabilityResult(
        cancellation_rate=cancellation_rate,
        return_rate=return_rate,
        dispatch_penalty=dispatch_penalty,
        reliability_score=score,
    )


DEFAULT_PRODUCT_WEIGHTS: dict[str, Decimal] = {
    "margin": Decimal("0.35"),
    "demand": Decimal("0.30"),
    "competition": Decimal("0.15"),
    "supplier_reliability": Decimal("0.20"),
}


@dataclass(frozen=True)
class ProductScoreResult:
    score: Decimal
    is_incomplete: bool
    missing_factors: tuple[str, ...]
    applied_weights: dict[str, Decimal]


def calculate_product_score(
    *,
    margin_score,
    demand_score,
    competition_score,
    supplier_reliability=None,
    weights: dict[str, Decimal] | None = None,
) -> ProductScoreResult:
    """Compute composite product score clamped to [0, 100].

    All factor inputs are expected on a 0–100 scale (out-of-range inputs are
    clamped after weighting so final score always lies in [0, 100]).
    If `supplier_reliability` (or any factor) is None, computes over available
    factors normalized by available weight and flags `is_incomplete=True`.
    """
    active_weights = dict(weights or DEFAULT_PRODUCT_WEIGHTS)
    raw_factors = {
        "margin": margin_score,
        "demand": demand_score,
        "competition": competition_score,
        "supplier_reliability": supplier_reliability,
    }

    present: dict[str, Decimal] = {}
    missing: list[str] = []

    for key, raw_val in raw_factors.items():
        if raw_val is None:
            missing.append(key)
        else:
            present[key] = _dec(raw_val, key)

    if not present:
        raise ValueError("At least one scoring factor must be provided")

    total_weight = sum((active_weights[k] for k in present), ZERO)
    if total_weight <= ZERO:
        raise ValueError("Sum of active weights must be positive")

    weighted = ZERO
    normalized_weights: dict[str, Decimal] = {}
    for key, val in present.items():
        norm_w = active_weights[key] / total_weight
        normalized_weights[key] = norm_w.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        weighted += val * norm_w

    final_score = _clamp(weighted).quantize(QUANT, rounding=ROUND_HALF_UP)
    return ProductScoreResult(
        score=final_score,
        is_incomplete=bool(missing),
        missing_factors=tuple(missing),
        applied_weights=normalized_weights,
    )
