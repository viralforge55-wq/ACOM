"""Server-authoritative cart validation & cart_token signing (API_CONTRACTS.md §3, R1–R4).

Invariants:
- Never accepts price, discount, tax, currency, or total from the browser.
- Strictly rejects AFFILIATE items from entering the dropshipping cart.
- Recomputes all prices strictly from ERPNext Item Price + Dropshipping Product using Decimal.
- Signs a 15-minute `cart_token` binding exact items and authoritative prices.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import frappe

from acom_core.affiliate_commerce.doctype.affiliate_network.affiliate_network import SLUG_PATTERN
from acom_core.api.errors import AcomApiError, format_money
from acom_core.dropshipping_commerce.doctype.dropshipping_product.dropshipping_product import (
    get_active_price_list_rate,
)
from acom_core.dropshipping_commerce.services.payment_gateway import (
    CART_TOKEN_TTL_SECONDS,
    get_cart_signing_secret,
)

PAISA = Decimal("0.01")
ZERO = Decimal("0.00")
MAX_ITEM_QTY = 25
ALLOWED_LINE_KEYS = frozenset({"product_slug", "quantity"})


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))


def sign_cart_token(payload: dict[str, Any]) -> str:
    encoded = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    sig = hmac.new(
        get_cart_signing_secret().encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"ct_{encoded}.{sig}"


def verify_cart_token(cart_token: str, *, now_ts: int | None = None) -> dict[str, Any]:
    raw = (cart_token or "").strip()
    if not raw.startswith("ct_") or "." not in raw:
        raise AcomApiError(
            "CART_EXPIRED",
            "Cart token is invalid or malformed.",
            status_code=422,
        )
    encoded, provided_sig = raw[3:].rsplit(".", 1)
    expected_sig = hmac.new(
        get_cart_signing_secret().encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_sig, provided_sig):
        raise AcomApiError(
            "CART_EXPIRED",
            "Cart token signature is invalid.",
            status_code=422,
        )
    try:
        decoded = json.loads(_b64url_decode(encoded).decode("utf-8"))
    except Exception as exc:
        raise AcomApiError(
            "CART_EXPIRED",
            "Cart token could not be decoded.",
            status_code=422,
        ) from exc

    current_ts = int(now_ts if now_ts is not None else time.time())
    issued_at = int(decoded.get("issued_at") or 0)
    if current_ts - issued_at > CART_TOKEN_TTL_SECONDS or current_ts < issued_at - 60:
        raise AcomApiError(
            "CART_EXPIRED",
            "Cart token has expired. Please re-validate your cart.",
            status_code=422,
        )
    return decoded


def validate_and_price_cart(
    items: Any,
    *,
    now_ts: int | None = None,
) -> dict[str, Any]:
    """Validate dropshipping cart items and compute authoritative server totals."""
    if not isinstance(items, list) or not 1 <= len(items) <= 25:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Cart must contain at least one item.",
            status_code=400,
            details={"fields": ["items"]},
        )

    merged_quantities: dict[str, int] = {}
    for idx, entry in enumerate(items, start=1):
        if not isinstance(entry, dict):
            raise AcomApiError(
                "VALIDATION_ERROR",
                f"Cart item {idx} must be an object.",
                status_code=400,
                details={"fields": [f"items[{idx}]"]},
            )
        unknown = sorted(k for k in entry.keys() if k not in ALLOWED_LINE_KEYS)
        if unknown:
            raise AcomApiError(
                "VALIDATION_ERROR",
                "Unknown or prohibited fields in cart item (prices/discounts cannot be supplied by client).",
                status_code=400,
                details={"fields": unknown},
            )

        slug = str(entry.get("product_slug") or "").strip().lower()
        if not slug or not SLUG_PATTERN.match(slug):
            raise AcomApiError(
                "VALIDATION_ERROR",
                "Invalid product_slug in cart.",
                status_code=400,
                details={"fields": ["product_slug"]},
            )

        qty_raw = entry.get("quantity")
        if isinstance(qty_raw, bool) or not isinstance(qty_raw, int) or qty_raw < 1 or qty_raw > MAX_ITEM_QTY:
            raise AcomApiError(
                "VALIDATION_ERROR",
                f"quantity must be an integer between 1 and {MAX_ITEM_QTY}.",
                status_code=400,
                details={"fields": ["quantity"]},
            )

        merged_quantities[slug] = merged_quantities.get(slug, 0) + qty_raw
        if merged_quantities[slug] > MAX_ITEM_QTY:
            raise AcomApiError(
                "VALIDATION_ERROR",
                f"Total quantity for '{slug}' exceeds limit ({MAX_ITEM_QTY}).",
                status_code=400,
                details={"fields": ["quantity"]},
            )

    lines: list[dict[str, Any]] = []
    token_lines: list[dict[str, Any]] = []
    internal_lines: list[dict[str, Any]] = []
    subtotal = ZERO
    currency = "INR"

    for slug, qty in merged_quantities.items():
        # Strictly reject AFFILIATE products from entering dropshipping cart!
        if frappe.db.exists("Affiliate Product", {"slug": slug}):
            raise AcomApiError(
                "PRODUCT_UNAVAILABLE",
                f"Affiliate product '{slug}' cannot be added to dropshipping cart.",
                status_code=422,
                details={"product_slug": slug, "sales_type": "AFFILIATE"},
            )

        prod = frappe.db.get_value(
            "Dropshipping Product",
            {"slug": slug},
            [
                "name",
                "product_name",
                "slug",
                "erpnext_item",
                "supplier",
                "supplier_sku",
                "selling_price",
                "supplier_cost",
                "price_list",
                "currency",
                "supplier_stock",
                "status",
                "lead_time_days",
            ],
            as_dict=True,
        )
        if not prod:
            raise AcomApiError(
                "NOT_FOUND",
                f"Product '{slug}' not found.",
                status_code=404,
                details={"product_slug": slug},
            )

        if prod["status"] != "Published":
            raise AcomApiError(
                "PRODUCT_UNAVAILABLE",
                f"Product '{slug}' is not currently published.",
                status_code=422,
                details={"product_slug": slug},
            )

        # Verify supplier & ERPNext Item mapping integrity
        item_ok = frappe.db.get_value("Item", prod["erpnext_item"], "disabled")
        sup_ok = frappe.db.get_value("Supplier", prod["supplier"], "disabled")
        if item_ok is None or item_ok or sup_ok is None or sup_ok or not prod.get("supplier_sku"):
            raise AcomApiError(
                "SUPPLIER_MAPPING_MISSING",
                f"Product '{slug}' has incomplete or disabled supplier mapping.",
                status_code=422,
                details={"product_slug": slug},
            )

        if int(prod.get("supplier_stock") or 0) < qty:
            raise AcomApiError(
                "OUT_OF_STOCK",
                f"Insufficient stock for '{slug}'.",
                status_code=422,
                details={"product_slug": slug},
            )

        # Authoritative price check against ERPNext Price List
        active_rate = get_active_price_list_rate(prod["erpnext_item"], prod["price_list"])
        declared_rate = Decimal(str(prod["selling_price"])).quantize(PAISA, rounding=ROUND_HALF_UP)
        if active_rate is None or active_rate != declared_rate:
            raise AcomApiError(
                "PRICE_MISMATCH",
                f"Price for '{slug}' is out of sync with authoritative Price List.",
                status_code=422,
                details={"product_slug": slug},
            )

        line_total = (active_rate * Decimal(qty)).quantize(PAISA, rounding=ROUND_HALF_UP)
        subtotal = (subtotal + line_total).quantize(PAISA, rounding=ROUND_HALF_UP)
        currency = (prod.get("currency") or "INR").upper()
        if currency != "INR" or not active_rate.is_finite() or active_rate <= ZERO:
            raise AcomApiError("PRODUCT_UNAVAILABLE", "Product pricing is invalid.", status_code=422)

        lines.append(
            {
                "product_slug": prod["slug"],
                "title": prod["product_name"],
                "quantity": qty,
                "unit_price": format_money(active_rate, currency),
                "line_total": format_money(line_total, currency),
                "available": True,
            }
        )
        token_lines.append(
            {
                "product_slug": prod["slug"],
                "quantity": qty,
                "unit_price": f"{active_rate:.2f}",
            }
        )
        internal_lines.append(
            {
                "dropshipping_product": prod["name"],
                "product_slug": prod["slug"],
                "product_title": prod["product_name"],
                "erpnext_item": prod["erpnext_item"],
                "supplier": prod["supplier"],
                "supplier_sku": prod["supplier_sku"],
                "quantity": qty,
                "unit_price": active_rate,
                "supplier_cost": Decimal(str(prod["supplier_cost"])).quantize(
                    PAISA, rounding=ROUND_HALF_UP
                ),
                "line_total": line_total,
                "lead_time_days": int(prod.get("lead_time_days") or 3),
            }
        )

    shipping = ZERO
    tax = ZERO
    total = (subtotal + shipping + tax).quantize(PAISA, rounding=ROUND_HALF_UP)

    issued_at = int(now_ts if now_ts is not None else time.time())
    cart_token = sign_cart_token(
        {
            "issued_at": issued_at,
            "currency": currency,
            "total": f"{total:.2f}",
            "lines": token_lines,
        }
    )

    return {
        "public": {
            "lines": lines,
            "subtotal": format_money(subtotal, currency),
            "shipping": format_money(shipping, currency),
            "tax": format_money(tax, currency),
            "total": format_money(total, currency),
            "cart_token": cart_token,
        },
        "internal": {
            "currency": currency,
            "subtotal": subtotal,
            "shipping": shipping,
            "tax": tax,
            "total": total,
            "lines": internal_lines,
        },
    }
