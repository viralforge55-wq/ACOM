"""Scheduled tasks and retry dispatchers for Integration Management & Automation."""

from __future__ import annotations

import frappe
from frappe.utils import now_datetime
from acom_core.integration_management.services.event_service import process_retry_queue
from acom_core.integration_management.workflows.order_monitor import run_order_monitor_flow
from acom_core.integration_management.workflows.reconciliation_monitor import run_reconciliation_monitor_flow
from acom_core.integration_management.workflows.supplier_monitor import run_supplier_monitor_flow


def retry_payment_events():
    """Phase 5 payment-outbox retry dispatcher."""
    for name in frappe.get_all(
        "Automation Event",
        filters={"event_type": "payment.confirmed", "processing_status": ["in", ["Received", "Failed"]]},
        fields=["name", "next_attempt_at"],
        limit=100,
    ):
        if name.next_attempt_at and name.next_attempt_at > now_datetime():
            continue
        frappe.enqueue(
            "acom_core.dropshipping_commerce.services.fulfillment_service.process_payment_confirmed_event",
            event_name=name.name,
            queue="short",
            timeout=120,
            job_id=f"acom-payment-{name.name}",
            enqueue_after_commit=True,
        )


def process_automation_retry_queue():
    """Phase 7 general automation outbox retry dispatcher."""
    return process_retry_queue(limit=50)


def run_scheduled_supplier_monitor():
    """Scheduled task: checks supplier stock and price changes."""
    # Pull published dropshipping products as mock feed baseline
    prods = frappe.get_all("Dropshipping Product", fields=["supplier_sku", "supplier_stock", "supplier_cost"], limit=100)
    feed_items = []
    for p in prods:
        if p.supplier_sku:
            feed_items.append({
                "supplier_sku": p.supplier_sku,
                "stock": p.supplier_stock,
                "cost": float(p.supplier_cost or 0),
            })
    if feed_items:
        return run_supplier_monitor_flow(feed_items=feed_items)
    return {"ok": True, "items_checked": 0}


def run_scheduled_order_monitor():
    """Scheduled task: checks stuck checkouts and stale draft POs."""
    return run_order_monitor_flow(stuck_checkout_minutes=30, stale_po_hours=24)


def run_scheduled_reconciliation_monitor():
    """Scheduled task: checks orphan conversions and overdue pending commissions."""
    return run_reconciliation_monitor_flow(overdue_pending_days=60)
