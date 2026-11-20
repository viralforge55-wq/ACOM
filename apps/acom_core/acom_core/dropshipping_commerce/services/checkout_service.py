"""Dropshipping checkout initiation & customer-scoped order lookup (API_CONTRACTS.md §3 & §6).

Invariants:
- Authenticated users only (`allow_guest=False`).
- Requires UUIDv4 `Idempotency-Key`:
    * Same key + same body -> HTTP 200 returning original checkout_id (I1)
    * Same key + different body -> HTTP 409 IDEMPOTENCY_CONFLICT (I2)
- Never trusts client-supplied price, discount, tax, currency, or totals (R1–R4).
- Always re-verifies live ERPNext Price List rates against signed `cart_token`.
- Never marks an order paid on checkout; stays `PendingPayment` until signed webhook confirms.
- Customer order lookup enforces strict owner scoping (`403 FORBIDDEN` for non-owners, A3).
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import frappe

from acom_core.api.errors import AcomApiError, format_money
from acom_core.dropshipping_commerce.services.cart_service import (
    validate_and_price_cart,
    verify_cart_token,
)
from acom_core.dropshipping_commerce.services.payment_gateway import create_test_gateway_order

PAISA = Decimal("0.01")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[+0-9][0-9\s-]{7,18}$")
PINCODE_RE = re.compile(r"^[0-9]{6}$")

ALLOWED_CHECKOUT_KEYS = frozenset(
    {"cart_token", "customer", "shipping_address", "payment_method", "expected_total"}
)
ALLOWED_CUSTOMER_KEYS = frozenset({"name", "email", "phone"})
ALLOWED_ADDRESS_KEYS = frozenset({"line1", "city", "state", "pincode", "country"})
ORDER_ADMIN_ROLES = frozenset({"System Manager", "ACOM Finance", "ACOM Manager"})


def _validate_uuid4(raw: str, field_name: str) -> str:
    cleaned = (raw or "").strip()
    try:
        parsed = uuid.UUID(cleaned, version=4)
        if str(parsed) != cleaned.lower():
            raise ValueError("not canonical")
    except ValueError as exc:
        raise AcomApiError(
            "VALIDATION_ERROR",
            f"{field_name} must be a valid UUIDv4.",
            status_code=400,
            details={"fields": [field_name]},
        ) from exc
    return cleaned.lower()


def _validate_customer_and_address(
    customer: Any, shipping_address: Any
) -> tuple[dict[str, str], dict[str, str]]:
    if not isinstance(customer, dict):
        raise AcomApiError(
            "VALIDATION_ERROR",
            "customer must be an object.",
            status_code=400,
            details={"fields": ["customer"]},
        )
    unknown_c = sorted(k for k in customer.keys() if k not in ALLOWED_CUSTOMER_KEYS)
    if unknown_c:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Unknown fields in customer object.",
            status_code=400,
            details={"fields": unknown_c},
        )
    cname = str(customer.get("name") or "").strip()
    cemail = str(customer.get("email") or "").strip().lower()
    cphone = str(customer.get("phone") or "").strip()
    if not cname or len(cname) > 140:
        raise AcomApiError("VALIDATION_ERROR", "customer.name is required.", status_code=400, details={"fields": ["customer.name"]})
    if not EMAIL_RE.match(cemail):
        raise AcomApiError("VALIDATION_ERROR", "customer.email must be a valid email.", status_code=400, details={"fields": ["customer.email"]})
    if not PHONE_RE.match(cphone):
        raise AcomApiError("VALIDATION_ERROR", "customer.phone must be a valid phone number.", status_code=400, details={"fields": ["customer.phone"]})

    if not isinstance(shipping_address, dict):
        raise AcomApiError(
            "VALIDATION_ERROR",
            "shipping_address must be an object.",
            status_code=400,
            details={"fields": ["shipping_address"]},
        )
    unknown_a = sorted(k for k in shipping_address.keys() if k not in ALLOWED_ADDRESS_KEYS)
    if unknown_a:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Unknown fields in shipping_address object.",
            status_code=400,
            details={"fields": unknown_a},
        )
    line1 = str(shipping_address.get("line1") or "").strip()
    city = str(shipping_address.get("city") or "").strip()
    state = str(shipping_address.get("state") or "").strip()
    pincode = str(shipping_address.get("pincode") or "").strip()
    country = str(shipping_address.get("country") or "IN").strip().upper()

    if not line1 or not city or not state:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "shipping_address requires line1, city, and state.",
            status_code=400,
            details={"fields": ["shipping_address"]},
        )
    if country != "IN" or not PINCODE_RE.match(pincode):
        raise AcomApiError(
            "VALIDATION_ERROR",
            "shipping_address.pincode must be a 6-digit Indian PIN code.",
            status_code=400,
            details={"fields": ["shipping_address.pincode"]},
        )
    if not pincode:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "shipping_address.pincode is required.",
            status_code=400,
            details={"fields": ["shipping_address.pincode"]},
        )

    return (
        {"name": cname, "email": cemail, "phone": cphone},
        {"line1": line1, "city": city, "state": state, "pincode": pincode, "country": country},
    )


def _format_checkout_response(doc) -> dict[str, Any]:
    total_dec = Decimal(str(doc.grand_total)).quantize(PAISA, rounding=ROUND_HALF_UP)
    return {
        "checkout_id": doc.name,
        "status": doc.status,
        "amount": format_money(total_dec, doc.currency or "INR"),
        "payment": {
            "provider": doc.payment_provider,
            "mode": "test",
            "order_ref": doc.gateway_order_ref,
        },
    }


def create_dropship_checkout(
    *,
    idempotency_key: str,
    body: dict[str, Any],
    now_ts: int | None = None,
) -> tuple[dict[str, Any], int]:
    """Create a PendingPayment Dropship Checkout idempotently."""
    if frappe.session.user == "Guest":
        raise AcomApiError("UNAUTHENTICATED", "Authentication required.", status_code=401)

    if not isinstance(body, dict):
        raise AcomApiError("VALIDATION_ERROR", "Request body must be a JSON object.", status_code=400)

    unknown = sorted(k for k in body.keys() if k not in ALLOWED_CHECKOUT_KEYS)
    if unknown:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Unknown or prohibited fields in checkout request (prices, discounts, and currency cannot be supplied by client).",
            status_code=400,
            details={"fields": unknown},
        )

    idem_key = _validate_uuid4(idempotency_key, "Idempotency-Key")
    cart_token = str(body.get("cart_token") or "").strip()
    payment_method = str(body.get("payment_method") or "gateway").strip().lower()
    if payment_method != "gateway":
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Only 'gateway' payment_method is supported.",
            status_code=400,
            details={"fields": ["payment_method"]},
        )

    customer, address = _validate_customer_and_address(
        body.get("customer"), body.get("shipping_address")
    )

    canonical_req = {
        "user": frappe.session.user,
        "cart_token": cart_token,
        "customer": customer,
        "shipping_address": address,
        "payment_method": payment_method,
        "expected_total": body.get("expected_total"),
    }
    request_hash = hashlib.sha256(
        json.dumps(canonical_req, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    # Check idempotency key FIRST (I1 & I2)
    existing_name = frappe.db.get_value(
        "Dropship Checkout", {"idempotency_key": idem_key}, "name"
    )
    if existing_name:
        existing_doc = frappe.get_doc("Dropship Checkout", existing_name)
        if existing_doc.request_hash != request_hash:
            raise AcomApiError(
                "IDEMPOTENCY_CONFLICT",
                "Idempotency-Key was already used with a different request payload.",
                status_code=409,
                details={"idempotency_key": idem_key},
            )
        return (_format_checkout_response(existing_doc), 200)

    # Verify cart_token signature & TTL (R2)
    token_data = verify_cart_token(cart_token, now_ts=now_ts)
    token_lines = token_data.get("lines") or []
    if not token_lines:
        raise AcomApiError("CART_EXPIRED", "Cart token contains no items.", status_code=422)

    # Recompute authoritative prices LIVE from ERPNext Price List + stock
    live = validate_and_price_cart(
        [{"product_slug": l["product_slug"], "quantity": l["quantity"]} for l in token_lines],
        now_ts=now_ts,
    )
    live_internal = live["internal"]

    # Reject if price changed after cart_token was issued (R2)
    live_prices = {line["product_slug"]: f"{line['unit_price']:.2f}" for line in live_internal["lines"]}
    if (f"{live_internal['total']:.2f}" != str(token_data.get("total"))
            or any(live_prices.get(line["product_slug"]) != line["unit_price"] for line in token_lines)):
        raise AcomApiError(
            "PRICE_MISMATCH",
            "Server price changed after cart validation. Please refresh your cart.",
            status_code=422,
        )

    # R1: if client supplied optional expected_total diagnostic and it differs -> reject PRICE_MISMATCH
    if body.get("expected_total") is not None:
        try:
            client_total = Decimal(str(body["expected_total"])).quantize(
                PAISA, rounding=ROUND_HALF_UP
            )
        except Exception as exc:
            raise AcomApiError(
                "VALIDATION_ERROR",
                "expected_total must be a valid decimal string.",
                status_code=400,
                details={"fields": ["expected_total"]},
            ) from exc
        if client_total != live_internal["total"]:
            raise AcomApiError(
                "PRICE_MISMATCH",
                "Client total does not match authoritative server total.",
                status_code=422,
            )

    gw_order = create_test_gateway_order(
        amount_str=f"{live_internal['total']:.2f}",
        currency=live_internal["currency"],
        checkout_ref=idem_key,
    )

    doc = frappe.get_doc(
        {
            "doctype": "Dropship Checkout",
            "idempotency_key": idem_key,
            "request_hash": request_hash,
            "status": "PendingPayment",
            "payment_provider": gw_order["provider"],
            "payment_method": payment_method,
            "gateway_order_ref": gw_order["order_ref"],
            "customer_user": frappe.session.user,
            "customer_name": customer["name"],
            "customer_email": customer["email"],
            "customer_phone": customer["phone"],
            "shipping_line1": address["line1"],
            "shipping_city": address["city"],
            "shipping_state": address["state"],
            "shipping_pincode": address["pincode"],
            "shipping_country": address["country"],
            "currency": live_internal["currency"],
            "subtotal": float(live_internal["subtotal"]),
            "shipping_total": float(live_internal["shipping"]),
            "tax_total": float(live_internal["tax"]),
            "grand_total": float(live_internal["total"]),
            "erp_sync_status": "NotStarted",
            "refund_status": "None",
            "items": [
                {
                    "dropshipping_product": line["dropshipping_product"],
                    "product_slug": line["product_slug"],
                    "product_title": line["product_title"],
                    "erpnext_item": line["erpnext_item"],
                    "supplier": line["supplier"],
                    "supplier_sku": line["supplier_sku"],
                    "quantity": line["quantity"],
                    "unit_price": float(line["unit_price"]),
                    "supplier_cost": float(line["supplier_cost"]),
                    "line_total": float(line["line_total"]),
                }
                for line in live_internal["lines"]
            ],
        }
    )

    try:
        doc.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        # Concurrent race winner (I4)
        winner_name = frappe.db.get_value(
            "Dropship Checkout", {"idempotency_key": idem_key}, "name"
        )
        winner = frappe.get_doc("Dropship Checkout", winner_name)
        if winner.request_hash != request_hash:
            raise AcomApiError(
                "IDEMPOTENCY_CONFLICT",
                "Idempotency-Key conflict.",
                status_code=409,
            )
        return (_format_checkout_response(winner), 200)

    resp = _format_checkout_response(doc)
    resp["payment"]["checkout_token"] = gw_order["checkout_token"]
    return (resp, 201)


def get_scoped_customer_order(order_id: str) -> dict[str, Any]:
    """Return customer-scoped order summary (API_CONTRACTS.md §6, TEST_PLAN A3).

    Owner or privileged manager only. Returns 403 (never 404) for non-owners to avoid
    leaking whether another customer's order exists.
    Never leaks supplier, supplier_sku, or supplier_cost.
    """
    if frappe.session.user == "Guest":
        raise AcomApiError("UNAUTHENTICATED", "Authentication required.", status_code=401)

    cleaned = (order_id or "").strip()
    if not cleaned:
        raise AcomApiError("FORBIDDEN", "Not permitted.", status_code=403)

    checkout_name = None
    if frappe.db.exists("Dropship Checkout", cleaned):
        checkout_name = cleaned
    else:
        checkout_name = frappe.db.get_value(
            "Dropship Checkout", {"sales_order": cleaned}, "name"
        )

    user_roles = set(frappe.get_roles(frappe.session.user))
    is_privileged = bool(user_roles.intersection(ORDER_ADMIN_ROLES))

    if not checkout_name:
        if is_privileged:
            raise AcomApiError("NOT_FOUND", "Order not found.", status_code=404)
        # Do not leak existence to non-privileged callers (API_CONTRACTS §6)
        raise AcomApiError("FORBIDDEN", "Not permitted.", status_code=403)

    doc = frappe.get_doc("Dropship Checkout", checkout_name)
    if doc.customer_user != frappe.session.user and not is_privileged:
        raise AcomApiError("FORBIDDEN", "Not permitted.", status_code=403)

    fulfillment: dict[str, Any] = {}
    if doc.carrier:
        fulfillment["carrier"] = doc.carrier
    if doc.tracking_number:
        fulfillment["tracking_number"] = doc.tracking_number
    if doc.tracking_url:
        fulfillment["tracking_url"] = doc.tracking_url
    if doc.estimated_delivery:
        fulfillment["estimated_delivery"] = str(doc.estimated_delivery)

    return {
        "checkout_id": doc.name,
        "order_id": doc.sales_order or doc.name,
        "status": doc.status,
        "placed_at": str(doc.creation),
        "lines": [
            {
                "product_slug": row.product_slug,
                "title": row.product_title,
                "quantity": int(row.quantity),
                "unit_price": format_money(row.unit_price, doc.currency or "INR"),
                "line_total": format_money(row.line_total, doc.currency or "INR"),
            }
            for row in doc.items
        ],
        "total": format_money(doc.grand_total, doc.currency or "INR"),
        "fulfillment": fulfillment,
        "refund_status": doc.refund_status or "None",
    }
