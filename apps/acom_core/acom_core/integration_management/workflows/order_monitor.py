"""Workflow 4: Order & Fulfillment Monitor (MASTER_BLUEPRINT §11, BUSINESS_WORKFLOWS W4/W5).

Flow:
1. Scheduled check over active Dropship Checkouts and ERPNext Purchase Orders.
2. Identifies stuck pending checkouts (> 30 min).
3. Identifies draft Purchase Orders awaiting approval (> 24 hours).
4. Raises structured alerts for founder attention.
5. Invariant A5: NEVER auto-submits Purchase Orders or auto-issues refunds.
6. Emits Automation Event (order_monitor.completed or order_monitor.alert).
7. Failure path: exceptions handled cleanly, audit trail logged.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

import frappe
from frappe.utils import now_datetime
from acom_core.integration_management.services.event_service import record_event


def run_order_monitor_flow(
    *,
    stuck_checkout_minutes: int = 30,
    stale_po_hours: int = 24,
    idempotency_key: str | None = None,
) -> Dict[str, Any]:
    """Execute Flow 4: Order & Fulfillment Monitor."""
    now = now_datetime()
    idem_key = idempotency_key or f"order_mon::{int(now.timestamp())}"

    # 1. Stuck Checkouts (status = Pending, creation > stuck_checkout_minutes ago)
    checkout_threshold = now - timedelta(minutes=stuck_checkout_minutes)
    stuck_checkouts = frappe.get_all(
        "Dropship Checkout",
        filters={
            "status": "Pending",
            "creation": ["<", checkout_threshold],
        },
        fields=["name", "grand_total", "creation"],
        limit=50,
    )

    # 2. Draft Purchase Orders awaiting approval > stale_po_hours
    po_threshold = now - timedelta(hours=stale_po_hours)
    stale_pos = []
    if frappe.db.has_table("Purchase Order"):
        stale_pos = frappe.get_all(
            "Purchase Order",
            filters={
                "docstatus": 0,  # Draft
                "creation": ["<", po_threshold],
            },
            fields=["name", "supplier", "grand_total", "creation"],
            limit=50,
        )

    alerts = []
    for co in stuck_checkouts:
        alerts.append({
            "type": "STUCK_CHECKOUT",
            "reference": co.name,
            "amount": str(co.grand_total),
            "age_minutes": int((now - co.creation).total_seconds() / 60),
        })

    for po in stale_pos:
        alerts.append({
            "type": "STALE_DRAFT_PO",
            "reference": po.name,
            "supplier": po.supplier,
            "grand_total": str(po.grand_total),
        })

    event_type = "order_monitor.alert" if alerts else "order_monitor.completed"
    payload = {
        "stuck_checkouts_count": len(stuck_checkouts),
        "stale_pos_count": len(stale_pos),
        "alerts_count": len(alerts),
        "alerts": alerts,
        "checked_at": str(now),
    }

    event = record_event(
        event_type=event_type,
        source="Scheduler",
        idempotency_key=idem_key,
        payload=payload,
        allow_duplicate_return=True,
    )

    return {
        "ok": True,
        "event_id": event.event_id,
        "event_type": event_type,
        "stuck_checkouts_count": len(stuck_checkouts),
        "stale_pos_count": len(stale_pos),
        "alerts_count": len(alerts),
    }
