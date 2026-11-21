"""Frappe Script Report: Supplier Performance Analytics.

Evaluates supplier fulfillment, lead time, and reliability metrics
per MASTER_BLUEPRINT §7, §12, §14, §20.
"""

from __future__ import annotations

from typing import Any

import frappe


def execute(filters: dict[str, Any] | None = None):
    f = filters or {}
    supplier = f.get("supplier")

    query_filters: dict[str, Any] = {}
    if supplier:
        query_filters["supplier"] = supplier

    suppliers = frappe.get_all(
        "Supplier Performance",
        filters=query_filters,
        fields=[
            "supplier",
            "orders_received",
            "orders_fulfilled",
            "avg_dispatch_hours",
            "cancellation_rate",
            "return_rate",
            "quality_issues",
            "reliability_score",
            "modified",
        ],
        order_by="reliability_score desc",
    )

    columns = [
        {"label": "Supplier", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 180},
        {"label": "Orders Received", "fieldname": "orders_received", "fieldtype": "Int", "width": 120},
        {"label": "Orders Fulfilled", "fieldname": "orders_fulfilled", "fieldtype": "Int", "width": 120},
        {"label": "Fulfillment %", "fieldname": "fulfillment_rate", "fieldtype": "Percent", "width": 110},
        {"label": "Avg Dispatch (Hrs)", "fieldname": "avg_dispatch_hours", "fieldtype": "Float", "width": 140},
        {"label": "Cancellation %", "fieldname": "cancellation_rate", "fieldtype": "Percent", "width": 120},
        {"label": "Return %", "fieldname": "return_rate", "fieldtype": "Percent", "width": 110},
        {"label": "Quality Issues", "fieldname": "quality_issues", "fieldtype": "Int", "width": 110},
        {"label": "Reliability Score", "fieldname": "reliability_score", "fieldtype": "Float", "width": 130},
        {"label": "Last Evaluated", "fieldname": "modified", "fieldtype": "Datetime", "width": 160},
    ]

    rows = []
    total_received = 0
    total_fulfilled = 0

    for s in suppliers:
        rec = int(s.get("orders_received") or 0)
        ful = int(s.get("orders_fulfilled") or 0)
        total_received += rec
        total_fulfilled += ful
        rate = round((ful / rec) * 100, 1) if rec > 0 else 100.0

        rows.append({
            "supplier": s["supplier"],
            "orders_received": rec,
            "orders_fulfilled": ful,
            "fulfillment_rate": rate,
            "avg_dispatch_hours": float(s.get("avg_dispatch_hours") or 0.0),
            "cancellation_rate": float(s.get("cancellation_rate") or 0.0),
            "return_rate": float(s.get("return_rate") or 0.0),
            "quality_issues": int(s.get("quality_issues") or 0),
            "reliability_score": float(s.get("reliability_score") or 0.0),
            "modified": s.get("modified"),
        })

    overall_ful = round((total_fulfilled / total_received) * 100, 1) if total_received > 0 else 100.0
    report_summary = [
        {"label": "Monitored Suppliers", "value": len(suppliers), "datatype": "Int"},
        {"label": "Total Orders Placed", "value": total_received, "datatype": "Int"},
        {"label": "Total Fulfilled", "value": total_fulfilled, "datatype": "Int", "indicator": "green"},
        {"label": "Overall Fulfillment Rate", "value": overall_ful, "datatype": "Percent", "indicator": "blue"},
    ]

    return columns, rows, None, None, report_summary
