"""Affiliate Reconciliation & Reporting service (DATA_DICTIONARY.md §4, W4, §12).

Financial & architectural invariants:
- Pure Frappe ORM + decimal.Decimal math (zero raw SQL, zero float drift).
- Bot-suspected clicks (`is_bot_suspected = 1`) are excluded from click denominators.
- `Pending` commission is NEVER included in confirmed or realized revenue.
- `Confirmed` and `Paid` enter `confirmed_revenue`, minus `Reversed` rows.
- `Paid` (realized) is broken out separately from unpaid `Confirmed` and `Pending`.
- ERPNext remains the sole authoritative accounting ledger; this service only
  reports and queues reconciliation items without posting ledger entries.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

import frappe
from frappe.utils import getdate, now_datetime

from acom_core.api.errors import AcomApiError, format_money

PAISA = Decimal("0.01")
ZERO = Decimal("0.00")

RECON_READ_ROLES = ("System Manager", "ACOM Finance", "ACOM Manager", "ACOM Analyst")
RECON_RESOLVE_ROLES = ("System Manager", "ACOM Finance", "ACOM Manager")


def _require_roles(allowed_roles: tuple[str, ...]) -> None:
    if frappe.session.user == "Guest":
        raise AcomApiError("UNAUTHENTICATED", "Authentication required.", status_code=401)
    user_roles = set(frappe.get_roles(frappe.session.user))
    if not user_roles.intersection(allowed_roles):
        raise AcomApiError("FORBIDDEN", "Not permitted.", status_code=403)


def _to_dec(value: Any) -> Decimal:
    if value is None or value == "":
        return ZERO
    return Decimal(str(value)).quantize(PAISA, rounding=ROUND_HALF_UP)


def _parse_optional_date(raw: str | None, field_name: str) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        return getdate(str(raw).strip()).isoformat()
    except Exception as exc:
        raise AcomApiError(
            "VALIDATION_ERROR",
            f"{field_name} must be a valid ISO date (YYYY-MM-DD).",
            status_code=400,
            details={"fields": [field_name]},
        ) from exc


def get_reconciliation_summary(
    *,
    affiliate_network: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    payout_expected: str | None = None,
    currency: str = "INR",
) -> dict[str, Any]:
    """Compute click vs conversion attribution and commission reconciliation summary."""
    _require_roles(RECON_READ_ROLES)

    net_filter = (affiliate_network or "").strip() or None
    if net_filter and not frappe.db.exists("Affiliate Network", net_filter):
        raise AcomApiError(
            "NOT_FOUND",
            f"Affiliate Network '{net_filter}' not found.",
            status_code=404,
            details={"fields": ["affiliate_network"]},
        )

    from_iso = _parse_optional_date(date_from, "date_from")
    to_iso = _parse_optional_date(date_to, "date_to")
    if from_iso and to_iso and getdate(to_iso) < getdate(from_iso):
        raise AcomApiError(
            "VALIDATION_ERROR",
            "date_to cannot be earlier than date_from.",
            status_code=400,
            details={"fields": ["date_from", "date_to"]},
        )

    expected_payout_dec: Decimal | None = None
    if payout_expected is not None and str(payout_expected).strip():
        try:
            expected_payout_dec = Decimal(str(payout_expected).strip()).quantize(
                PAISA, rounding=ROUND_HALF_UP
            )
            if expected_payout_dec < ZERO:
                raise ValueError("negative")
        except (InvalidOperation, ValueError) as exc:
            raise AcomApiError(
                "VALIDATION_ERROR",
                "payout_expected must be a non-negative decimal string.",
                status_code=400,
                details={"fields": ["payout_expected"]},
            ) from exc

    # 1. Click metrics (filter by network via product links when network filter is set)
    click_filters: dict[str, Any] = {}
    if net_filter:
        net_products = frappe.get_all(
            "Affiliate Product",
            filters={"affiliate_network": net_filter},
            pluck="name",
        )
        click_filters["affiliate_product"] = ["in", net_products or ["__none__"]]

    if from_iso and to_iso:
        click_filters["clicked_at"] = ["between", [f"{from_iso} 00:00:00", f"{to_iso} 23:59:59"]]
    elif from_iso:
        click_filters["clicked_at"] = [">=", f"{from_iso} 00:00:00"]
    elif to_iso:
        click_filters["clicked_at"] = ["<=", f"{to_iso} 23:59:59"]

    click_rows = frappe.get_all(
        "Affiliate Click",
        filters=click_filters,
        fields=["name", "attribution_status", "is_bot_suspected"],
    )

    valid_clicks = 0
    bot_clicks_excluded = 0
    click_status_counts = {"Recorded": 0, "Matched": 0, "Unmatched": 0, "Expired": 0}
    for row in click_rows:
        if row.get("is_bot_suspected"):
            bot_clicks_excluded += 1
            continue
        valid_clicks += 1
        st = row.get("attribution_status") or "Recorded"
        if st in click_status_counts:
            click_status_counts[st] += 1

    # 2. Conversion & Commission metrics
    conv_filters: dict[str, Any] = {}
    if net_filter:
        conv_filters["affiliate_network"] = net_filter
    if from_iso and to_iso:
        conv_filters["conversion_date"] = ["between", [from_iso, to_iso]]
    elif from_iso:
        conv_filters["conversion_date"] = [">=", from_iso]
    elif to_iso:
        conv_filters["conversion_date"] = ["<=", to_iso]

    conv_rows = frappe.get_all(
        "Affiliate Conversion",
        filters=conv_filters,
        fields=[
            "name",
            "affiliate_network",
            "network_conversion_id",
            "affiliate_product",
            "affiliate_click",
            "conversion_date",
            "currency",
            "order_value",
            "commission_amount",
            "commission_status",
            "matched_by",
            "needs_manual_review",
            "raw_subid",
            "raw_product_sku",
            "payment_reference",
            "reversed_conversion",
        ],
        order_by="conversion_date desc, creation desc",
    )

    totals = {
        "Pending": ZERO,
        "Confirmed": ZERO,
        "Paid": ZERO,
        "Rejected": ZERO,
        "Reversed": ZERO,
    }
    counts = {
        "Pending": 0,
        "Confirmed": 0,
        "Paid": 0,
        "Rejected": 0,
        "Reversed": 0,
    }
    attributed_conversions = 0
    unmatched_conversions = 0
    manual_review_queue: list[dict[str, Any]] = []
    conversion_rows_out: list[dict[str, Any]] = []

    target_currency = (currency or "INR").upper()

    for row in conv_rows:
        status = row.get("commission_status") or "Pending"
        amount = _to_dec(row.get("commission_amount"))
        if status in totals:
            totals[status] += amount
            counts[status] += 1

        # Reversal rows are adjustments, not additional customer conversions
        if status != "Reversed":
            if row.get("matched_by") == "Unmatched" or row.get("needs_manual_review"):
                unmatched_conversions += 1
                manual_review_queue.append(
                    {
                        "conversion_id": row["name"],
                        "network": row["affiliate_network"],
                        "network_conversion_id": row["network_conversion_id"],
                        "conversion_date": str(row["conversion_date"]),
                        "raw_subid": row.get("raw_subid") or "",
                        "raw_product_sku": row.get("raw_product_sku") or "",
                        "commission_status": status,
                        "commission_amount": format_money(amount, row.get("currency") or target_currency),
                    }
                )
            else:
                attributed_conversions += 1

        conversion_rows_out.append(
            {
                "conversion_id": row["name"],
                "network": row["affiliate_network"],
                "network_conversion_id": row["network_conversion_id"],
                "affiliate_product": row.get("affiliate_product") or "",
                "affiliate_click": row.get("affiliate_click") or "",
                "conversion_date": str(row["conversion_date"]),
                "matched_by": row.get("matched_by") or "Unmatched",
                "commission_status": status,
                "commission_amount": format_money(amount, row.get("currency") or target_currency),
                "payment_reference": row.get("payment_reference") or "",
            }
        )

    # Pending is NEVER revenue. Confirmed revenue = Confirmed + Paid - Reversed.
    confirmed_revenue = (totals["Confirmed"] + totals["Paid"] - totals["Reversed"]).quantize(
        PAISA, rounding=ROUND_HALF_UP
    )
    realized_paid = totals["Paid"].quantize(PAISA, rounding=ROUND_HALF_UP)

    total_non_reversal_conversions = attributed_conversions + unmatched_conversions
    if valid_clicks > 0:
        conv_rate_pct = (
            Decimal(attributed_conversions) / Decimal(valid_clicks) * Decimal("100")
        ).quantize(PAISA, rounding=ROUND_HALF_UP)
    else:
        conv_rate_pct = ZERO

    payout_check: dict[str, Any] = {}
    if expected_payout_dec is not None:
        variance = (realized_paid - expected_payout_dec).quantize(PAISA, rounding=ROUND_HALF_UP)
        payout_check = {
            "expected_payout": format_money(expected_payout_dec, target_currency),
            "paid_commission": format_money(realized_paid, target_currency),
            "variance": format_money(variance, target_currency),
            "has_exception": variance != ZERO,
        }

    return {
        "accounting_ledger_authority": "ERPNext",
        "filters": {
            "affiliate_network": net_filter or "",
            "date_from": from_iso or "",
            "date_to": to_iso or "",
        },
        "clicks": {
            "total_valid_clicks": valid_clicks,
            "bot_clicks_excluded": bot_clicks_excluded,
            "matched_clicks": click_status_counts["Matched"],
            "recorded_clicks": click_status_counts["Recorded"],
            "expired_clicks": click_status_counts["Expired"],
            "unmatched_clicks": click_status_counts["Unmatched"],
        },
        "conversions": {
            "total_conversions": total_non_reversal_conversions,
            "attributed_conversions": attributed_conversions,
            "unmatched_conversions": unmatched_conversions,
            "reversal_rows": counts["Reversed"],
            "conversion_rate_pct": f"{conv_rate_pct:.2f}",
            "counts_by_status": counts,
        },
        "commissions": {
            "pending": format_money(totals["Pending"], target_currency),
            "confirmed": format_money(totals["Confirmed"], target_currency),
            "paid": format_money(realized_paid, target_currency),
            "rejected": format_money(totals["Rejected"], target_currency),
            "reversed": format_money(totals["Reversed"], target_currency),
            "confirmed_revenue": format_money(confirmed_revenue, target_currency),
            "realized_revenue": format_money(realized_paid, target_currency),
        },
        "payout_check": payout_check,
        "manual_review_queue": manual_review_queue,
        "transactions": conversion_rows_out,
    }


def resolve_unmatched_conversion(
    *,
    conversion_name: str,
    affiliate_product: str | None = None,
    affiliate_click: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Manually link an orphan conversion to a product/click with audit trail."""
    _require_roles(RECON_RESOLVE_ROLES)

    conv_id = (conversion_name or "").strip()
    if not conv_id or not frappe.db.exists("Affiliate Conversion", conv_id):
        raise AcomApiError("NOT_FOUND", "Affiliate Conversion not found.", status_code=404)

    prod_id = (affiliate_product or "").strip() or None
    click_id = (affiliate_click or "").strip() or None

    if not prod_id and not click_id:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Provide affiliate_product or affiliate_click to resolve the unmatched conversion.",
            status_code=400,
            details={"fields": ["affiliate_product", "affiliate_click"]},
        )

    if click_id:
        click_meta = frappe.db.get_value(
            "Affiliate Click",
            click_id,
            ["name", "affiliate_product", "campaign_id", "attribution_status"],
            as_dict=True,
        )
        if not click_meta:
            raise AcomApiError("NOT_FOUND", "Affiliate Click not found.", status_code=404)
        prod_id = prod_id or click_meta["affiliate_product"]
        if click_meta["attribution_status"] != "Matched":
            click_doc = frappe.get_doc("Affiliate Click", click_id)
            click_doc.attribution_status = "Matched"
            click_doc.save(ignore_permissions=True)

    if prod_id and not frappe.db.exists("Affiliate Product", prod_id):
        raise AcomApiError("NOT_FOUND", "Affiliate Product not found.", status_code=404)

    campaign = (
        frappe.db.get_value("Affiliate Product", prod_id, "campaign") if prod_id else None
    )

    doc = frappe.get_doc("Affiliate Conversion", conv_id)
    doc.affiliate_product = prod_id
    doc.affiliate_click = click_id
    doc.campaign = campaign
    doc.matched_by = "Manual"
    doc.needs_manual_review = 0
    doc.append(
        "status_history",
        {
            "from_status": doc.commission_status,
            "to_status": doc.commission_status,
            "changed_at": now_datetime(),
            "changed_by": frappe.session.user,
            "import_batch": doc.import_batch,
            "note": (note or "").strip() or f"Manual match to {prod_id or click_id}",
        },
    )
    doc.save()

    return {
        "conversion_id": doc.name,
        "affiliate_product": doc.affiliate_product or "",
        "affiliate_click": doc.affiliate_click or "",
        "matched_by": doc.matched_by,
        "needs_manual_review": bool(doc.needs_manual_review),
    }
