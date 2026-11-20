"""Frappe Script Report: Affiliate Commission Reconciliation.

Uses pure ORM + Decimal reconciliation_service (zero raw SQL).
Separates Pending, Confirmed, Paid (realized), Rejected, and Reversed commissions.
"""

from __future__ import annotations

from typing import Any

from acom_core.affiliate_commerce.services.reconciliation_service import (
    get_reconciliation_summary,
)


def execute(filters: dict[str, Any] | None = None):
    f = filters or {}
    summary = get_reconciliation_summary(
        affiliate_network=f.get("affiliate_network"),
        date_from=f.get("date_from"),
        date_to=f.get("date_to"),
    )

    columns = [
        {"label": "Conversion ID", "fieldname": "conversion_id", "fieldtype": "Link", "options": "Affiliate Conversion", "width": 170},
        {"label": "Network", "fieldname": "network", "fieldtype": "Link", "options": "Affiliate Network", "width": 160},
        {"label": "Network Txn ID", "fieldname": "network_conversion_id", "fieldtype": "Data", "width": 160},
        {"label": "Date", "fieldname": "conversion_date", "fieldtype": "Date", "width": 110},
        {"label": "Matched By", "fieldname": "matched_by", "fieldtype": "Data", "width": 100},
        {"label": "Product", "fieldname": "affiliate_product", "fieldtype": "Link", "options": "Affiliate Product", "width": 140},
        {"label": "Status", "fieldname": "commission_status", "fieldtype": "Data", "width": 110},
        {"label": "Commission", "fieldname": "commission_amount", "fieldtype": "Currency", "width": 120},
        {"label": "Payment Ref", "fieldname": "payment_reference", "fieldtype": "Data", "width": 140},
    ]

    rows = [
        {
            "conversion_id": t["conversion_id"],
            "network": t["network"],
            "network_conversion_id": t["network_conversion_id"],
            "conversion_date": t["conversion_date"],
            "matched_by": t["matched_by"],
            "affiliate_product": t["affiliate_product"],
            "commission_status": t["commission_status"],
            "commission_amount": float(t["commission_amount"]["amount"]),
            "payment_reference": t["payment_reference"],
        }
        for t in summary["transactions"]
    ]

    comm = summary["commissions"]
    report_summary = [
        {"label": "Valid Clicks", "value": summary["clicks"]["total_valid_clicks"], "datatype": "Int"},
        {"label": "Attributed Conversions", "value": summary["conversions"]["attributed_conversions"], "datatype": "Int"},
        {"label": "Pending (Not Revenue)", "value": float(comm["pending"]["amount"]), "datatype": "Currency", "indicator": "orange"},
        {"label": "Confirmed Revenue", "value": float(comm["confirmed_revenue"]["amount"]), "datatype": "Currency", "indicator": "blue"},
        {"label": "Paid (Realized)", "value": float(comm["paid"]["amount"]), "datatype": "Currency", "indicator": "green"},
        {"label": "Rejected", "value": float(comm["rejected"]["amount"]), "datatype": "Currency", "indicator": "red"},
    ]

    return columns, rows, None, None, report_summary
