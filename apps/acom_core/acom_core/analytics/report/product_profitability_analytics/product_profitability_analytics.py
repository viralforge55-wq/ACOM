"""Frappe Script Report: Product Profitability Analytics.

Ranks products across Dropshipping and Affiliate channels by contribution profit
per MASTER_BLUEPRINT §4, §12, §14, §20.
"""

from __future__ import annotations

from typing import Any

from acom_core.analytics.services.profitability_service import get_product_profitability_report


def execute(filters: dict[str, Any] | None = None):
    f = filters or {}
    channel = f.get("channel")
    date_from = f.get("date_from")
    date_to = f.get("date_to")

    report = get_product_profitability_report(
        channel=channel,
        date_from=date_from,
        date_to=date_to,
        limit=200,
    )

    columns = [
        {"label": "Product", "fieldname": "product_name", "fieldtype": "Data", "width": 220},
        {"label": "Channel", "fieldname": "channel", "fieldtype": "Data", "width": 110},
        {"label": "Units / Convs", "fieldname": "units_sold", "fieldtype": "Int", "width": 100},
        {"label": "Gross Revenue", "fieldname": "gross_revenue", "fieldtype": "Currency", "width": 130},
        {"label": "Supplier Cost", "fieldname": "supplier_cost", "fieldtype": "Currency", "width": 130},
        {"label": "Contribution Profit", "fieldname": "contribution_profit", "fieldtype": "Currency", "width": 150},
        {"label": "Margin %", "fieldname": "contribution_margin_pct", "fieldtype": "Percent", "width": 100},
        {"label": "Drill-Through Rows", "fieldname": "drill_through_count", "fieldtype": "Int", "width": 130},
    ]

    rows = [
        {
            "product_name": r["product_name"],
            "channel": r["channel"],
            "units_sold": r["units_sold"],
            "gross_revenue": float(r["gross_revenue"]["amount"]),
            "supplier_cost": float(r["supplier_cost"]["amount"]),
            "contribution_profit": float(r["contribution_profit"]["amount"]),
            "contribution_margin_pct": r["contribution_margin_pct"],
            "drill_through_count": len(r["drill_through_rows"]),
        }
        for r in report["ranking"]
    ]

    s = report["summary"]
    report_summary = [
        {"label": "Monitored Products", "value": s["products_count"], "datatype": "Int"},
        {"label": "Total Revenue", "value": float(s["total_revenue"]["amount"]), "datatype": "Currency", "indicator": "green"},
        {"label": "Total Contribution Profit", "value": float(s["total_contribution_profit"]["amount"]), "datatype": "Currency", "indicator": "blue"},
        {"label": "Overall Margin", "value": s["overall_margin_pct"], "datatype": "Percent", "indicator": "blue"},
    ]

    return columns, rows, None, None, report_summary
