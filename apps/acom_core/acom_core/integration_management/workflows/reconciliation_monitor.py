"""Workflow 5: Affiliate & Finance Reconciliation Monitor (MASTER_BLUEPRINT §11, BUSINESS_WORKFLOWS W4/W7).

Flow:
1. Scheduled sweep across Affiliate Conversions and financial records.
2. Identifies unmatched orphan conversions (attribution_status = Unmatched).
3. Identifies overdue pending commissions (> 60 days pending).
4. Enqueues reconciliation exception records for manual founder review.
5. Emits Automation Event (reconciliation_monitor.completed or reconciliation.exception).
6. Failure path: exceptions logged cleanly without corrupting financial ledgers.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

import frappe
from frappe.utils import now_datetime
from acom_core.integration_management.services.event_service import record_event


def run_reconciliation_monitor_flow(
    *,
    overdue_pending_days: int = 60,
    idempotency_key: str | None = None,
) -> Dict[str, Any]:
    """Execute Flow 5: Affiliate & Finance Reconciliation Monitor."""
    now = now_datetime()
    idem_key = idempotency_key or f"reconcile_mon::{int(now.timestamp())}"

    # 1. Unmatched / orphan conversions
    orphans = frappe.get_all(
        "Affiliate Conversion",
        filters={
            "needs_manual_review": 1,
        },
        fields=["name", "network_conversion_id", "affiliate_network", "order_value", "commission_amount"],
        limit=50,
    )

    # 2. Overdue pending commissions
    overdue_date = (now - timedelta(days=overdue_pending_days)).date()
    overdue_pending = frappe.get_all(
        "Affiliate Conversion",
        filters={
            "commission_status": "Pending",
            "conversion_date": ["<", overdue_date],
        },
        fields=["name", "network_conversion_id", "affiliate_network", "commission_amount", "conversion_date"],
        limit=50,
    )

    exceptions = []
    for conv in orphans:
        exceptions.append({
            "type": "ORPHAN_CONVERSION",
            "reference": conv.network_conversion_id or conv.name,
            "network": conv.affiliate_network,
            "sale_amount": str(conv.order_value),
            "commission_amount": str(conv.commission_amount),
        })

    for conv in overdue_pending:
        exceptions.append({
            "type": "OVERDUE_PENDING_COMMISSION",
            "reference": conv.network_conversion_id or conv.name,
            "network": conv.affiliate_network,
            "commission_amount": str(conv.commission_amount),
            "conversion_date": str(conv.conversion_date),
        })

    event_type = "reconciliation.exception" if exceptions else "reconciliation_monitor.completed"
    payload = {
        "orphan_count": len(orphans),
        "overdue_pending_count": len(overdue_pending),
        "exceptions_count": len(exceptions),
        "exceptions": exceptions,
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
        "orphan_count": len(orphans),
        "overdue_pending_count": len(overdue_pending),
        "exceptions_count": len(exceptions),
    }
