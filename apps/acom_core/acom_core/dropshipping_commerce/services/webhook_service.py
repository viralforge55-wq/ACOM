"""Signed Payment Gateway Webhook processor (API_CONTRACTS.md §4, gates G4/G5, P1–P9).

Invariants:
- Signature is verified over RAW REQUEST BYTES BEFORE JSON parsing.
- Timestamp window enforced (±300s -> WEBHOOK_STALE).
- Replay/duplicate `X-Event-Id` is enforced via unique-indexed `Automation Event.idempotency_key`
  and returns HTTP 200 `{ duplicate: true }` with zero state change.
- Amount, currency, and order_ref are verified exact to paisa against the local pending checkout.
- On verified capture: writes `Automation Event(payment.confirmed)` + marks checkout Paid,
  then triggers downstream ERPNext SO/PO execution.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

import frappe
from frappe.utils import now_datetime

from acom_core.api.errors import AcomApiError
from acom_core.dropshipping_commerce.services.fulfillment_service import (
    process_payment_confirmed_event,
)
from acom_core.dropshipping_commerce.services.payment_gateway import verify_webhook_signature

PAISA = Decimal("0.01")


def handle_payment_webhook(
    *,
    raw_body: bytes,
    signature: str,
    timestamp: str,
    event_id: str,
    now_ts: int | None = None,
) -> tuple[dict[str, Any], int]:
    """Verify HMAC signature over raw bytes, enforce idempotency, and execute payment confirmation."""
    clean_event_id = (event_id or "").strip()
    if not clean_event_id:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "X-Event-Id header is required.",
            status_code=400,
            details={"fields": ["X-Event-Id"]},
        )

    valid, err_code = verify_webhook_signature(
        timestamp=timestamp,
        raw_body=raw_body,
        signature=signature,
        now_ts=now_ts,
    )
    if not valid:
        status_code = 400 if err_code == "WEBHOOK_STALE" else 401
        raise AcomApiError(
            err_code or "INVALID_SIGNATURE",
            "Payment webhook signature or timestamp verification failed.",
            status_code=status_code,
        )

    # Replay / duplicate check BEFORE mutating any state (I3, P5)
    idem_key = f"payment_webhook::{clean_event_id}"
    if frappe.db.exists("Automation Event", {"idempotency_key": idem_key}):
        return (
            {"duplicate": True, "event_id": clean_event_id},
            200,
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Webhook body must be valid JSON.",
            status_code=400,
        ) from exc

    if not isinstance(payload, dict) or set(payload) - {"order_ref", "payment_id", "amount", "currency", "status"}:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Webhook payload must be a JSON object.",
            status_code=400,
        )

    order_ref = str(payload.get("order_ref") or "").strip()
    payment_id = str(payload.get("payment_id") or "").strip()
    currency = str(payload.get("currency") or "").strip().upper()
    payment_status = str(payload.get("status") or "").strip().lower()
    if not payment_id or len(payment_id) > 140 or payment_status not in {"captured", "failed", "authorized"}:
        raise AcomApiError("WEBHOOK_MISMATCH", "Invalid transaction reference or status.", status_code=400)

    try:
        paid_amount = Decimal(str(payload.get("amount"))).quantize(PAISA, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AcomApiError(
            "WEBHOOK_MISMATCH",
            "Invalid payment amount in webhook payload.",
            status_code=400,
        ) from exc

    checkout_name = frappe.db.get_value(
        "Dropship Checkout", {"gateway_order_ref": order_ref}, "name", for_update=True
    )
    if not checkout_name:
        raise AcomApiError(
            "WEBHOOK_MISMATCH",
            "Unknown gateway order_ref.",
            status_code=400,
            details={"order_ref": order_ref},
        )

    checkout = frappe.get_doc("Dropship Checkout", checkout_name)
    expected_amount = Decimal(str(checkout.grand_total)).quantize(PAISA, rounding=ROUND_HALF_UP)
    expected_currency = (checkout.currency or "INR").upper()

    if not paid_amount.is_finite() or paid_amount != expected_amount or currency != "INR" or currency != expected_currency:
        frappe.log_error(
            title=f"ACOM webhook mismatch for {checkout.name}",
            message=(
                f"Expected {expected_amount} {expected_currency}, "
                f"received {paid_amount} {currency} (event={clean_event_id})"
            ),
        )
        raise AcomApiError(
            "WEBHOOK_MISMATCH",
            "Webhook amount or currency does not match pending checkout.",
            status_code=400,
        )

    if payment_status != "captured":
        evt = frappe.get_doc(
            {
                "doctype": "Automation Event",
                "event_id": str(uuid.uuid4()),
                "event_type": f"payment.{payment_status or 'unknown'}",
                "source": "PaymentGateway",
                "aggregate_doctype": "Dropship Checkout",
                "aggregate_name": checkout.name,
                "idempotency_key": idem_key,
                "payload": json.dumps(
                    {
                        "checkout_id": checkout.name,
                        "order_ref": order_ref,
                        "payment_id": payment_id,
                        "status": payment_status,
                    }
                ),
                "processing_status": "Completed",
                "processed_at": now_datetime(),
            }
        )
        evt.insert(ignore_permissions=True)
        return (
            {
                "duplicate": False,
                "event_id": clean_event_id,
                "checkout_id": checkout.name,
                "status": checkout.status,
            },
            200,
        )

    # Serialize captures by checkout, including retries using a different event header.
    if checkout.gateway_payment_id:
        if checkout.gateway_payment_id != payment_id:
            raise AcomApiError("WEBHOOK_MISMATCH", "Checkout already has a different capture.", status_code=409)
        return ({"duplicate": True, "event_id": clean_event_id}, 200)
    if checkout.status != "PendingPayment":
        raise AcomApiError("WEBHOOK_MISMATCH", "Checkout cannot accept a capture.", status_code=409)
    if frappe.db.exists("Dropship Checkout", {"gateway_payment_id": payment_id}):
        raise AcomApiError("WEBHOOK_MISMATCH", "Transaction already assigned.", status_code=409)

    # Verified payment capture: write Automation Event outbox + mark checkout Paid in same transaction
    outbox = frappe.get_doc(
        {
            "doctype": "Automation Event",
            "event_id": str(uuid.uuid4()),
            "event_type": "payment.confirmed",
            "source": "PaymentGateway",
            "aggregate_doctype": "Dropship Checkout",
            "aggregate_name": checkout.name,
            "idempotency_key": idem_key,
            "payload": json.dumps(
                {
                    "checkout_id": checkout.name,
                    "order_ref": order_ref,
                    "payment_id": payment_id or f"gw_pay_{clean_event_id}",
                    "amount": f"{paid_amount:.2f}",
                    "currency": currency,
                }
            ),
            "processing_status": "Received",
        }
    )
    try:
        outbox.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        return ({"duplicate": True, "event_id": clean_event_id}, 200)

    if checkout.status == "PendingPayment":
        checkout.status = "Paid"
        checkout.gateway_payment_id = payment_id or f"gw_pay_{clean_event_id}"
        checkout.paid_at = now_datetime()
        checkout.save(ignore_permissions=True)

    # The worker runs only after the capture and outbox commit together.
    frappe.enqueue(
        "acom_core.dropshipping_commerce.services.fulfillment_service.process_payment_confirmed_event",
        event_name=outbox.name, queue="short", timeout=120,
        job_id=f"acom-payment-{outbox.name}", enqueue_after_commit=True,
    )

    return (
        {
            "duplicate": False,
            "event_id": clean_event_id,
            "checkout_id": checkout.name,
            "erp_sync_status": "ERP_PENDING",
        },
        200,
    )
