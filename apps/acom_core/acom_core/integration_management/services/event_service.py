"""Event Outbox Service & Dispatcher (DATA_DICTIONARY.md §10, ADR-0002).

Guarantees:
- DB-backed idempotency key deduplication (409 DUPLICATE on collision).
- Transactional event recording.
- Exponential backoff retry for failed events.
- Dead-letter state after max retries (5).
- Handler registration and dispatching.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Callable, Dict

import frappe
from frappe.utils import now_datetime
from acom_core.api.errors import AcomApiError

EVENT_HANDLERS: Dict[str, Callable[[Any], Any]] = {}
MAX_RETRIES = 5


def register_event_handler(event_type: str, handler: Callable[[Any], Any]) -> None:
    """Register a handler function for an automation event type."""
    EVENT_HANDLERS[event_type] = handler


def record_event(
    *,
    event_type: str,
    source: str,
    idempotency_key: str,
    payload: dict[str, Any],
    aggregate_doctype: str | None = None,
    aggregate_name: str | None = None,
    allow_duplicate_return: bool = False,
) -> Any:
    """Record an Automation Event into the outbox.

    If allow_duplicate_return is True and the key exists, returns the existing event.
    Otherwise raises AcomApiError(409, "DUPLICATE_EVENT").
    """
    clean_idem = (idempotency_key or "").strip()
    if not clean_idem:
        raise AcomApiError("VALIDATION_ERROR", "idempotency_key is required.", status_code=400)

    # Check for duplicate
    existing_name = frappe.db.get_value("Automation Event", {"idempotency_key": clean_idem}, "name")
    if existing_name:
        if allow_duplicate_return:
            return frappe.get_doc("Automation Event", existing_name)
        raise AcomApiError(
            "DUPLICATE_EVENT",
            f"Event with idempotency_key '{clean_idem}' already exists.",
            status_code=409,
            details={"idempotency_key": clean_idem, "existing_event": existing_name},
        )

    doc = frappe.get_doc({
        "doctype": "Automation Event",
        "event_type": event_type,
        "source": source,
        "idempotency_key": clean_idem,
        "aggregate_doctype": aggregate_doctype,
        "aggregate_name": aggregate_name,
        "processing_status": "Received",
        "retry_count": 0,
        "payload": json.dumps(payload) if isinstance(payload, dict) else payload,
        "created_at": now_datetime(),
    })
    doc.insert(ignore_permissions=True)
    return doc


def dispatch_event(event_name: str) -> dict[str, Any]:
    """Dispatch a single Automation Event to its registered handler."""
    if not frappe.db.exists("Automation Event", event_name):
        raise AcomApiError("NOT_FOUND", f"Automation Event {event_name} not found.", status_code=404)

    doc = frappe.get_doc("Automation Event", event_name)

    if doc.processing_status == "Completed":
        return {"status": "already_completed", "event_id": doc.event_id}

    if doc.processing_status == "Dead Letter":
        return {"status": "dead_letter", "event_id": doc.event_id}

    # Transition to Processing
    doc.processing_status = "Processing"
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    handler = EVENT_HANDLERS.get(doc.event_type)
    if not handler:
        # No handler registered; treat as completed (passive audit event)
        doc.processing_status = "Completed"
        doc.processed_at = now_datetime()
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {"status": "completed", "event_id": doc.event_id, "handler": None}

    try:
        raw_payload = doc.payload
        payload_data = json.loads(raw_payload) if isinstance(raw_payload, str) else (raw_payload or {})
        handler_result = handler(payload_data)

        doc.processing_status = "Completed"
        doc.processed_at = now_datetime()
        doc.error_details = None
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {"status": "completed", "event_id": doc.event_id, "result": handler_result}

    except Exception as exc:
        frappe.db.rollback()
        # Reload doc after rollback to record error
        doc = frappe.get_doc("Automation Event", event_name)
        doc.retry_count = (doc.retry_count or 0) + 1

        if doc.retry_count >= MAX_RETRIES:
            doc.processing_status = "Dead Letter"
            doc.next_attempt_at = None
        else:
            doc.processing_status = "Failed"
            # Exponential backoff: 2 ** retry_count minutes (e.g. 2, 4, 8, 16, 32 min)
            backoff_sec = min(3600, (2 ** doc.retry_count) * 60)
            doc.next_attempt_at = now_datetime() + timedelta(seconds=backoff_sec)

        doc.error_details = f"{type(exc).__name__}: {str(exc)}"[:1000]
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {"status": doc.processing_status, "event_id": doc.event_id, "error": doc.error_details}


def process_retry_queue(limit: int = 50) -> dict[str, int]:
    """Scan and process pending/failed retryable Automation Events."""
    now = now_datetime()

    events = frappe.get_all(
        "Automation Event",
        filters={
            "processing_status": ["in", ["Received", "Failed"]],
            "retry_count": ["<", MAX_RETRIES],
        },
        fields=["name", "next_attempt_at"],
        order_by="created_at asc",
        limit=limit,
    )

    succeeded = 0
    failed = 0
    skipped = 0

    for ev in events:
        if ev.next_attempt_at and ev.next_attempt_at > now:
            skipped += 1
            continue

        try:
            res = dispatch_event(ev.name)
            if res.get("status") == "completed":
                succeeded += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    return {"processed": len(events) - skipped, "succeeded": succeeded, "failed": failed, "skipped": skipped}
