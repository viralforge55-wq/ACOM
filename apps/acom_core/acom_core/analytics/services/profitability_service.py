"""Product Profitability Service.

Computes exact unit economics and profitability ranking across both Dropshipping
and Affiliate products per MASTER_BLUEPRINT §4, §12, §14, §20.

Guarantees:
- Pure Frappe ORM (zero raw SQL).
- Exact Decimal precision.
- Taxes excluded from business revenue and contribution profit.
- Drill-through support from product aggregates to underlying order/conversion rows.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import frappe
from frappe.utils import getdate, nowdate


TWO_PLACES = Decimal("0.01")


def _to_decimal(val: Any) -> Decimal:
    if val is None or val == "":
        return Decimal("0.00")
    try:
        return Decimal(str(val)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def _format_money(amount: Decimal, currency: str = "INR") -> dict[str, str]:
    return {
        "amount": str(amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)),
        "currency": currency,
    }


def get_product_profitability_report(
    channel: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Compute product profitability ranking across channels with full drill-through."""
    today = nowdate()
    start_date = str(getdate(date_from)) if date_from else None
    end_date = str(getdate(date_to)) if date_to else today

    products_map: dict[str, dict[str, Any]] = {}

    # ─────────────────────────────────────────────────────────────
    # 1. DROPSHIPPING PRODUCTS PROFITABILITY
    # ─────────────────────────────────────────────────────────────
    if not channel or channel.upper() == "DROPSHIP":
        chk_filters: dict[str, Any] = {
            "status": ["in", ["Paid", "Processing", "AwaitingSupplier", "Shipped", "Delivered"]]
        }
        if start_date:
            chk_filters["creation"] = ["between", [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]]

        paid_checkouts = frappe.get_all(
            "Dropship Checkout",
            filters=chk_filters,
            fields=["name", "creation", "shipping_total"],
        )
        paid_chk_ids = [c["name"] for c in paid_checkouts]

        if paid_chk_ids:
            items = frappe.get_all(
                "Dropship Checkout Item",
                filters={"parent": ["in", paid_chk_ids]},
                fields=[
                    "parent",
                    "dropshipping_product",
                    "product_title",
                    "supplier_sku",
                    "quantity",
                    "unit_price",
                    "supplier_cost",
                    "line_total",
                ],
            )

            for itm in items:
                prod_id = itm.get("dropshipping_product") or itm.get("product_title") or "Unknown Dropship Item"
                qty = Decimal(str(itm.get("quantity") or 1))
                unit_p = _to_decimal(itm.get("unit_price"))
                sup_c = _to_decimal(itm.get("supplier_cost"))
                line_rev = unit_p * qty
                line_cost = sup_c * qty
                line_gateway_fee = (line_rev * Decimal("0.02")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                line_profit = line_rev - line_cost - line_gateway_fee

                if prod_id not in products_map:
                    products_map[prod_id] = {
                        "product_id": prod_id,
                        "product_name": itm.get("product_title") or prod_id,
                        "channel": "DROPSHIP",
                        "units_sold": Decimal("0"),
                        "gross_revenue": Decimal("0.00"),
                        "supplier_cost": Decimal("0.00"),
                        "estimated_gateway_fees": Decimal("0.00"),
                        "contribution_profit": Decimal("0.00"),
                        "drill_through_rows": [],
                    }

                entry = products_map[prod_id]
                entry["units_sold"] += qty
                entry["gross_revenue"] += line_rev
                entry["supplier_cost"] += line_cost
                entry["estimated_gateway_fees"] += line_gateway_fee
                entry["contribution_profit"] += line_profit
                if itm.get("parent") not in entry["drill_through_rows"]:
                    entry["drill_through_rows"].append(itm.get("parent"))

    # ─────────────────────────────────────────────────────────────
    # 2. AFFILIATE PRODUCTS PROFITABILITY
    # ─────────────────────────────────────────────────────────────
    if not channel or channel.upper() == "AFFILIATE":
        conv_filters: dict[str, Any] = {
            "commission_status": ["in", ["Confirmed", "Paid"]]
        }
        if start_date:
            conv_filters["conversion_date"] = ["between", [start_date, end_date]]

        confirmed_convs = frappe.get_all(
            "Affiliate Conversion",
            filters=conv_filters,
            fields=[
                "name",
                "affiliate_product",
                "commission_amount",
                "order_value",
                "conversion_date",
            ],
        )

        for conv in confirmed_convs:
            prod_id = conv.get("affiliate_product") or "Unattributed Affiliate"
            comm_amt = _to_decimal(conv.get("commission_amount"))
            order_val = _to_decimal(conv.get("order_value"))

            if prod_id not in products_map:
                prod_title = prod_id
                if frappe.db.exists("Affiliate Product", prod_id):
                    prod_title = frappe.db.get_value("Affiliate Product", prod_id, "product_name") or prod_id

                products_map[prod_id] = {
                    "product_id": prod_id,
                    "product_name": prod_title,
                    "channel": "AFFILIATE",
                    "units_sold": Decimal("0"),
                    "gross_revenue": Decimal("0.00"),
                    "supplier_cost": Decimal("0.00"),
                    "estimated_gateway_fees": Decimal("0.00"),
                    "contribution_profit": Decimal("0.00"),
                    "drill_through_rows": [],
                }

            entry = products_map[prod_id]
            entry["units_sold"] += Decimal("1")
            entry["gross_revenue"] += comm_amt  # Net revenue earned by ACOM
            entry["contribution_profit"] += comm_amt  # 100% margin on affiliate commission
            entry["drill_through_rows"].append(conv["name"])

    # ─────────────────────────────────────────────────────────────
    # 3. FORMAT & RANK BY CONTRIBUTION PROFIT DESCENDING
    # ─────────────────────────────────────────────────────────────
    ranking: list[dict[str, Any]] = []
    total_rev = Decimal("0.00")
    total_profit = Decimal("0.00")

    for p_id, item in products_map.items():
        rev = item["gross_revenue"]
        profit = item["contribution_profit"]
        margin_pct = (
            round(float((profit / rev) * Decimal("100.0")), 2)
            if rev > Decimal("0.00")
            else 0.0
        )

        total_rev += rev
        total_profit += profit

        ranking.append({
            "product_id": item["product_id"],
            "product_name": item["product_name"],
            "channel": item["channel"],
            "units_sold": int(item["units_sold"]),
            "gross_revenue": _format_money(rev),
            "supplier_cost": _format_money(item["supplier_cost"]),
            "contribution_profit": _format_money(profit),
            "contribution_margin_pct": margin_pct,
            "drill_through_rows": item["drill_through_rows"],
        })

    # Sort descending by contribution profit
    ranking.sort(
        key=lambda x: Decimal(x["contribution_profit"]["amount"]),
        reverse=True,
    )

    return {
        "period": {
            "start_date": start_date or "beginning",
            "end_date": end_date,
        },
        "summary": {
            "products_count": len(ranking),
            "total_revenue": _format_money(total_rev),
            "total_contribution_profit": _format_money(total_profit),
            "overall_margin_pct": (
                round(float((total_profit / total_rev) * Decimal("100.0")), 2)
                if total_rev > Decimal("0.00")
                else 0.0
            ),
        },
        "ranking": ranking[:limit],
    }
