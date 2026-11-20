"""Bounded payment-outbox retry dispatcher; Phase 5 reliability only."""
import frappe
from frappe.utils import now_datetime


def retry_payment_events():
    for name in frappe.get_all(
        "Automation Event",
        filters={"event_type": "payment.confirmed", "processing_status": ["in", ["Received", "Failed"]]},
        fields=["name", "next_attempt_at"], limit=100,
    ):
        if name.next_attempt_at and name.next_attempt_at > now_datetime():
            continue
        frappe.enqueue(
            "acom_core.dropshipping_commerce.services.fulfillment_service.process_payment_confirmed_event",
            event_name=name.name, queue="short", timeout=120,
            job_id=f"acom-payment-{name.name}", enqueue_after_commit=True,
        )
