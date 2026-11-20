"""Dropshipping Cart, Checkout, Payment Webhook, Fulfillment & Order APIs (API_CONTRACTS.md §3, §4, §6).

Routes via Frappe:
- POST /api/method/acom_core.api.dropship.validate_cart       (public read-only validation)
- POST /api/method/acom_core.api.dropship.create_checkout     (authenticated + Idempotency-Key)
- GET  /api/method/acom_core.api.dropship.get_customer_order  (authenticated, owner-scoped A3)
- POST /api/method/acom_core.api.dropship.payment_webhook     (HMAC-SHA256 over raw bytes, G4/G5)
- POST /api/method/acom_core.api.dropship.approve_purchase_order (System Manager / Finance / Manager)
- POST /api/method/acom_core.api.dropship.update_tracking     (System Manager / Manager)
- POST /api/method/acom_core.api.dropship.request_refund      (owner or manager)
- POST /api/method/acom_core.api.dropship.decide_refund       (System Manager / Finance ONLY)
"""

from __future__ import annotations

import json
from typing import Any

import frappe

from acom_core.api.errors import AcomApiError, error_response, ok_response
from acom_core.dropshipping_commerce.services.cart_service import validate_and_price_cart
from acom_core.dropshipping_commerce.services.checkout_service import (
    create_dropship_checkout,
    get_scoped_customer_order,
)
from acom_core.dropshipping_commerce.services.fulfillment_service import (
    approve_and_submit_purchase_order,
    approve_or_reject_refund,
    request_cancellation_or_refund,
    update_fulfillment_tracking,
)
from acom_core.dropshipping_commerce.services.webhook_service import handle_payment_webhook

_FRAPPE_INTERNAL_PARAMS = frozenset({"cmd", "_"})


@frappe.whitelist(methods=["GET"])
def session_info():
    from frappe.sessions import get_csrf_token
    return ok_response({"csrf_token": get_csrf_token()}, status_code=200)


@frappe.whitelist(methods=["POST"])
def simulate_test_payment(checkout_id: str):
    """Local gateway simulator. Only owner, explicit site opt-in, test mode only."""
    import time
    from acom_core.dropshipping_commerce.services.payment_gateway import get_payment_mode, compute_webhook_signature
    if get_payment_mode() != "test" or not frappe.conf.get("acom_enable_payment_simulator"):
        return error_response("FORBIDDEN", "Payment simulator disabled.", status_code=403)
    try:
        get_scoped_customer_order(checkout_id)
        checkout = frappe.get_doc("Dropship Checkout", checkout_id)
        if checkout.customer_user != frappe.session.user:
            raise AcomApiError("FORBIDDEN", "Not permitted.", status_code=403)
        raw = json.dumps({"order_ref": checkout.gateway_order_ref,
            "payment_id": "test-capture-" + checkout.name, "amount": f"{checkout.grand_total:.2f}",
            "currency": "INR", "status": "captured"}, separators=(",", ":")).encode()
        timestamp = str(int(time.time()))
        data, status = handle_payment_webhook(raw_body=raw, timestamp=timestamp,
            signature=compute_webhook_signature(timestamp, raw), event_id="test-event-" + checkout.name)
        return ok_response(data, status_code=status)
    except AcomApiError as exc:
        frappe.db.rollback()
        return exc.to_response()


def _extract_json_body(explicit_kwargs: dict[str, Any]) -> dict[str, Any]:
    request = getattr(frappe.local, "request", None)
    if request is not None and request.data:
        try:
            parsed = json.loads(request.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AcomApiError(
                "VALIDATION_ERROR",
                "Request body must be valid JSON.",
                status_code=400,
            ) from exc
        if not isinstance(parsed, dict):
            raise AcomApiError(
                "VALIDATION_ERROR",
                "Request body must be a JSON object.",
                status_code=400,
            )
        return parsed

    form = getattr(frappe.local, "form_dict", None)
    if form:
        filtered = {k: v for k, v in form.items() if k not in _FRAPPE_INTERNAL_PARAMS}
        if filtered:
            return filtered

    return {k: v for k, v in explicit_kwargs.items() if v is not None}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def validate_cart(items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Server-authoritative cart validation (maps to POST /api/cart/validate)."""
    try:
        body = _extract_json_body({"items": items})
        unknown = sorted(k for k in body.keys() if k != "items")
        if unknown:
            raise AcomApiError(
                "VALIDATION_ERROR",
                "Unknown fields in cart validation request.",
                status_code=400,
                details={"fields": unknown},
            )
        result = validate_and_price_cart(body.get("items"))
        return ok_response(result["public"], status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM validate_cart unexpected error")
        return error_response("INTERNAL_ERROR", "An unexpected error occurred.", status_code=500)


@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_checkout(
    cart_token: str | None = None,
    customer: dict[str, Any] | None = None,
    shipping_address: dict[str, Any] | None = None,
    payment_method: str | None = None,
    expected_total: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Authenticated idempotent checkout initiation (maps to POST /api/checkout)."""
    try:
        body = _extract_json_body(
            {
                "cart_token": cart_token,
                "customer": customer,
                "shipping_address": shipping_address,
                "payment_method": payment_method,
                "expected_total": expected_total,
            }
        )
        req = getattr(frappe.local, "request", None)
        header_idem = req.headers.get("Idempotency-Key") if req is not None else None
        effective_idem = (header_idem or idempotency_key or "").strip()

        data, status_code = create_dropship_checkout(
            idempotency_key=effective_idem,
            body=body,
        )
        return ok_response(data, status_code=status_code)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM create_checkout unexpected error")
        return error_response("INTERNAL_ERROR", "An unexpected error occurred.", status_code=500)


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_customer_order(order_id: str = "") -> dict[str, Any]:
    """Customer-scoped order read (maps to GET /api/orders/{order_id}, gate A3)."""
    try:
        data = get_scoped_customer_order(order_id=order_id)
        return ok_response(data, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM get_customer_order unexpected error")
        return error_response("INTERNAL_ERROR", "An unexpected error occurred.", status_code=500)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def payment_webhook() -> dict[str, Any]:
    """Server-to-server signed payment webhook (maps to POST /api/internal/payments/webhook).

    Authentication is strictly HMAC-SHA256 over raw request bytes before JSON parsing (G4/G5).
    """
    try:
        req = getattr(frappe.local, "request", None)
        if req is None:
            raise AcomApiError("VALIDATION_ERROR", "HTTP request context required.", status_code=400)

        raw_body = req.get_data(cache=True) or b""
        signature = req.headers.get("X-Signature") or ""
        timestamp = req.headers.get("X-Timestamp") or ""
        event_id = req.headers.get("X-Event-Id") or ""

        data, status_code = handle_payment_webhook(
            raw_body=raw_body,
            signature=signature,
            timestamp=timestamp,
            event_id=event_id,
        )
        return ok_response(data, status_code=status_code)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM payment_webhook unexpected error")
        return error_response("INTERNAL_ERROR", "An unexpected error occurred.", status_code=500)


@frappe.whitelist(allow_guest=False, methods=["POST"])
def approve_purchase_order(checkout_id: str = "", note: str = "") -> dict[str, Any]:
    """Authorized approval to submit the Draft supplier Purchase Order."""
    try:
        body = _extract_json_body({"checkout_id": checkout_id, "note": note})
        data = approve_and_submit_purchase_order(
            checkout_id=str(body.get("checkout_id") or ""),
            note=str(body.get("note") or ""),
        )
        return ok_response(data, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM approve_purchase_order unexpected error")
        return error_response("INTERNAL_ERROR", "An unexpected error occurred.", status_code=500)


@frappe.whitelist(allow_guest=False, methods=["POST"])
def update_tracking(
    checkout_id: str = "",
    carrier: str = "",
    tracking_number: str = "",
    tracking_url: str = "",
    estimated_delivery: str | None = None,
    status: str = "Shipped",
) -> dict[str, Any]:
    """Authorized update of supplier tracking and fulfillment status."""
    try:
        body = _extract_json_body(
            {
                "checkout_id": checkout_id,
                "carrier": carrier,
                "tracking_number": tracking_number,
                "tracking_url": tracking_url,
                "estimated_delivery": estimated_delivery,
                "status": status,
            }
        )
        data = update_fulfillment_tracking(
            checkout_id=str(body.get("checkout_id") or ""),
            carrier=str(body.get("carrier") or ""),
            tracking_number=str(body.get("tracking_number") or ""),
            tracking_url=str(body.get("tracking_url") or ""),
            estimated_delivery=body.get("estimated_delivery"),
            status=str(body.get("status") or "Shipped"),
        )
        return ok_response(data, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM update_tracking unexpected error")
        return error_response("INTERNAL_ERROR", "An unexpected error occurred.", status_code=500)


@frappe.whitelist(allow_guest=False, methods=["POST"])
def request_refund(
    checkout_id: str = "",
    reason: str = "",
    refund_amount: str | None = None,
) -> dict[str, Any]:
    """Cancel an unpaid checkout or open an approval-gated refund request."""
    try:
        body = _extract_json_body(
            {
                "checkout_id": checkout_id,
                "reason": reason,
                "refund_amount": refund_amount,
            }
        )
        data = request_cancellation_or_refund(
            checkout_id=str(body.get("checkout_id") or ""),
            reason=str(body.get("reason") or ""),
            refund_amount=body.get("refund_amount"),
        )
        return ok_response(data, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM request_refund unexpected error")
        return error_response("INTERNAL_ERROR", "An unexpected error occurred.", status_code=500)


@frappe.whitelist(allow_guest=False, methods=["POST"])
def decide_refund(
    checkout_id: str = "",
    decision: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Authorized approval/rejection of a refund request (System Manager / ACOM Finance ONLY)."""
    try:
        body = _extract_json_body(
            {"checkout_id": checkout_id, "decision": decision, "note": note}
        )
        data = approve_or_reject_refund(
            checkout_id=str(body.get("checkout_id") or ""),
            decision=str(body.get("decision") or ""),
            note=str(body.get("note") or ""),
        )
        return ok_response(data, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM decide_refund unexpected error")
        return error_response("INTERNAL_ERROR", "An unexpected error occurred.", status_code=500)
