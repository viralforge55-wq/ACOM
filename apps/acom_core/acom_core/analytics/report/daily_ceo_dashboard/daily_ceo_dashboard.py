"""Frappe Script Report: Daily CEO Dashboard.

Consolidates all executive KPIs into one unified Frappe Desk view per MASTER_BLUEPRINT §14, §20.
Traceable to underlying rows (TEST_PLAN Gate 8).
Revenue separated from pending commissions (TEST_PLAN Gate F5).
"""

from __future__ import annotations

from typing import Any

from acom_core.analytics.services.ceo_dashboard_service import get_ceo_dashboard_summary


def execute(filters: dict[str, Any] | None = None):
    f = filters or {}
    period = f.get("period") or "today"
    date_from = f.get("date_from")
    date_to = f.get("date_to")

    summary = get_ceo_dashboard_summary(
        period=period,
        date_from=date_from,
        date_to=date_to,
    )

    columns = [
        {"label": "Metric Category", "fieldname": "category", "fieldtype": "Data", "width": 180},
        {"label": "Key Indicator", "fieldname": "metric_name", "fieldtype": "Data", "width": 240},
        {"label": "Count / Value", "fieldname": "value_display", "fieldtype": "Data", "width": 160},
        {"label": "Status / Risk", "fieldname": "status_indicator", "fieldtype": "Data", "width": 140},
        {"label": "Drill-Through Target", "fieldname": "drill_through_key", "fieldtype": "Data", "width": 180},
    ]

    comm = summary["commerce"]
    fin = summary["financial"]
    aff = summary["affiliate_performance"]
    sup = summary["supplier_performance"]
    ai = summary["ai_and_exceptions"]

    rows = [
        # Commerce
        {"category": "Commerce", "metric_name": "Today's Orders", "value_display": f"{comm['orders_today_count']} orders (₹{comm['orders_today_value']['amount']})", "status_indicator": "Active", "drill_through_key": "orders_today"},
        {"category": "Commerce", "metric_name": "Pending Checkouts", "value_display": f"{comm['pending_checkouts_count']} (₹{comm['pending_checkouts_value']['amount']})", "status_indicator": "Pending", "drill_through_key": "pending_checkouts"},
        {"category": "Commerce", "metric_name": "Orders Awaiting Supplier Action", "value_display": f"{comm['awaiting_supplier_action_count']} draft POs", "status_indicator": "Action Required" if comm["awaiting_supplier_action_count"] > 0 else "OK", "drill_through_key": "awaiting_supplier_action"},
        {"category": "Commerce", "metric_name": "Delayed Shipments", "value_display": f"{comm['delayed_shipments_count']} shipments", "status_indicator": "Alert" if comm["delayed_shipments_count"] > 0 else "OK", "drill_through_key": "delayed_shipments"},
        # Financial
        {"category": "Financial Control", "metric_name": "Gross Customer Payments", "value_display": f"₹{fin['customer_paid_gross']['amount']}", "status_indicator": "Captured", "drill_through_key": "paid_checkouts"},
        {"category": "Financial Control", "metric_name": "Confirmed Dropship Revenue (Excl Tax)", "value_display": f"₹{fin['confirmed_dropship_revenue']['amount']}", "status_indicator": "Confirmed", "drill_through_key": "paid_checkouts"},
        {"category": "Financial Control", "metric_name": "Confirmed Affiliate Commission", "value_display": f"₹{fin['confirmed_affiliate_commission']['amount']}", "status_indicator": "Reconciled", "drill_through_key": "confirmed_conversions"},
        {"category": "Financial Control", "metric_name": "Total Confirmed Revenue", "value_display": f"₹{fin['total_confirmed_revenue']['amount']}", "status_indicator": "Net Revenue", "drill_through_key": "confirmed_conversions"},
        {"category": "Financial Control", "metric_name": "Estimated Pending Commission (Not Revenue)", "value_display": f"₹{fin['estimated_pending_commission']['amount']}", "status_indicator": "Pending Recon", "drill_through_key": "pending_conversions"},
        {"category": "Financial Control", "metric_name": "Dropshipping Supplier Cost Payable", "value_display": f"₹{fin['supplier_cost_payable']['amount']}", "status_indicator": "Payable", "drill_through_key": "paid_checkouts"},
        {"category": "Financial Control", "metric_name": "Refunds & Reversals", "value_display": f"₹{fin['refunds_total']['amount']}", "status_indicator": "Refunded" if float(fin["refunds_total"]["amount"]) > 0 else "None", "drill_through_key": "refunded_checkouts"},
        {"category": "Financial Control", "metric_name": "Actual Contribution Profit", "value_display": f"₹{fin['contribution_profit']['amount']} ({fin['contribution_margin_pct']}%)", "status_indicator": "Healthy" if float(fin["contribution_profit"]["amount"]) >= 0 else "Loss", "drill_through_key": "paid_checkouts"},
        {"category": "Financial Control", "metric_name": "Net Cash Position", "value_display": f"₹{fin['net_cash_position']['amount']}", "status_indicator": "Liquid", "drill_through_key": "paid_checkouts"},
        # Affiliate
        {"category": "Affiliate Traffic", "metric_name": "Affiliate Clicks (Period / Today)", "value_display": f"{aff['clicks_total_count']} / {aff['clicks_today_count']}", "status_indicator": "Traffic", "drill_through_key": "affiliate_clicks"},
        {"category": "Affiliate Traffic", "metric_name": "Attributed Conversions & Rate", "value_display": f"{aff['attributed_conversions_count']} conversions ({aff['conversion_rate_pct']}%)", "status_indicator": "Attributed", "drill_through_key": "confirmed_conversions"},
        # Supplier
        {"category": "Supplier Intelligence", "metric_name": "Monitored Suppliers", "value_display": f"{sup['monitored_suppliers_count']} active suppliers", "status_indicator": f"{sup['average_reliability_score']}/100 Avg", "drill_through_key": "supplier_performance"},
        {"category": "Supplier Intelligence", "metric_name": "Stockout Products", "value_display": f"{sup['stockout_products_count']} out of stock", "status_indicator": "Warning" if sup["stockout_products_count"] > 0 else "Normal", "drill_through_key": "stockout_products"},
        # AI & Exceptions
        {"category": "AI Operations", "metric_name": "AI Tasks (Succeeded / Failed)", "value_display": f"{ai['ai_tasks_succeeded']} / {ai['ai_tasks_failed']}", "status_indicator": "OK" if ai["ai_tasks_failed"] == 0 else "Attention", "drill_through_key": "failed_ai_tasks"},
        {"category": "AI Operations", "metric_name": "Pending Approval Requests", "value_display": f"{ai['pending_approvals_count']} approvals (High/Crit: {ai['pending_approvals_by_risk']['High'] + ai['pending_approvals_by_risk']['Critical']})", "status_indicator": "Queue Pending" if ai["pending_approvals_count"] > 0 else "Clean", "drill_through_key": "pending_approvals"},
        {"category": "System Exceptions", "metric_name": "Dead-Letter Automation Events", "value_display": f"{ai['outbox_dead_letter_count']} dead letters", "status_indicator": "CRITICAL" if ai["outbox_dead_letter_count"] > 0 else "Clean", "drill_through_key": "dead_letter_events"},
    ]

    report_summary = [
        {"label": "Confirmed Revenue", "value": float(fin["total_confirmed_revenue"]["amount"]), "datatype": "Currency", "indicator": "green"},
        {"label": "Contribution Profit", "value": float(fin["contribution_profit"]["amount"]), "datatype": "Currency", "indicator": "blue"},
        {"label": "Estimated Pending Comm.", "value": float(fin["estimated_pending_commission"]["amount"]), "datatype": "Currency", "indicator": "orange"},
        {"label": "Orders Today", "value": comm["orders_today_count"], "datatype": "Int", "indicator": "blue"},
        {"label": "Awaiting Supplier", "value": comm["awaiting_supplier_action_count"], "datatype": "Int", "indicator": "orange" if comm["awaiting_supplier_action_count"] > 0 else "green"},
        {"label": "Pending AI Approvals", "value": ai["pending_approvals_count"], "datatype": "Int", "indicator": "orange" if ai["pending_approvals_count"] > 0 else "green"},
        {"label": "Dead Letters", "value": ai["outbox_dead_letter_count"], "datatype": "Int", "indicator": "red" if ai["outbox_dead_letter_count"] > 0 else "green"},
    ]

    return columns, rows, None, None, report_summary
