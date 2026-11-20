"""Test-mode Payment Gateway adapter & HMAC-SHA256 verification (SECURITY_POLICY.md §6).

Invariants:
- Operates strictly in test mode (`PAYMENT_MODE=test`) for local PoC.
- Never accepts, processes, logs, or stores card numbers, CVV, or UPI PINs.
- HMAC-SHA256 signatures are verified over raw request bytes using constant-time compare.
- Timestamp window enforced to ±300 seconds to block replay attacks.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
import uuid

import frappe

WEBHOOK_MAX_SKEW_SECONDS = 300
CART_TOKEN_TTL_SECONDS = 15 * 60


def get_payment_mode() -> str:
    mode = (
        os.environ.get("PAYMENT_MODE")
        or frappe.conf.get("acom_payment_mode")
        or "test"
    ).strip().lower()
    return mode


def get_webhook_secret() -> str:
    secret = (
        os.environ.get("ACOM_PAYMENT_WEBHOOK_SECRET")
        or frappe.conf.get("acom_payment_webhook_secret")
        or ""
    ).strip()
    if secret:
        return secret
    raise RuntimeError("ACOM payment webhook secret is not configured.")


def get_cart_signing_secret() -> str:
    secret = (
        os.environ.get("ACOM_CART_SIGNING_SECRET")
        or frappe.conf.get("acom_cart_signing_secret")
        or ""
    ).strip()
    if secret:
        return secret
    raise RuntimeError("ACOM cart signing secret is not configured.")


def compute_webhook_signature(timestamp: str, raw_body: bytes, secret: str | None = None) -> str:
    key = (secret if secret is not None else get_webhook_secret()).encode("utf-8")
    message = f"{timestamp}.".encode("utf-8") + raw_body
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def verify_webhook_signature(
    *,
    timestamp: str,
    raw_body: bytes,
    signature: str,
    now_ts: int | None = None,
    secret: str | None = None,
) -> tuple[bool, str | None]:
    """Verify HMAC-SHA256 signature and timestamp window (±300s).

    Returns (True, None) on success or (False, error_code) on failure.
    """
    if not signature or not timestamp:
        return (False, "INVALID_SIGNATURE")

    try:
        ts_int = int(str(timestamp).strip())
    except (TypeError, ValueError):
        return (False, "WEBHOOK_STALE")

    current_ts = int(now_ts if now_ts is not None else time.time())
    if abs(current_ts - ts_int) > WEBHOOK_MAX_SKEW_SECONDS:
        return (False, "WEBHOOK_STALE")

    expected = compute_webhook_signature(str(ts_int), raw_body, secret=secret)
    provided = signature.strip()
    if provided.startswith("sha256="):
        provided = provided[7:]

    if not hmac.compare_digest(expected.lower(), provided.lower()):
        return (False, "INVALID_SIGNATURE")

    return (True, None)


def create_test_gateway_order(*, amount_str: str, currency: str, checkout_ref: str) -> dict[str, str]:
    """Create a simulated test-mode payment gateway order reference."""
    if get_payment_mode() != "test":
        raise RuntimeError("Live payment gateway mode is blocked until Phase 5 exit approval.")
    order_ref = f"gw_ord_{uuid.uuid4().hex[:16]}"
    checkout_token = f"gw_tok_{uuid.uuid4().hex[:20]}"
    return {
        "provider": "test_gateway",
        "mode": "test",
        "order_ref": order_ref,
        "checkout_token": checkout_token,
        "amount": amount_str,
        "currency": currency,
        "reference": checkout_ref,
    }


def create_test_gateway_refund(*, payment_id: str, amount_str: str, currency: str) -> dict[str, str]:
    """Simulate a test-mode payment gateway refund after authorized approval."""
    if get_payment_mode() != "test":
        raise RuntimeError("Live payment gateway mode is blocked until Phase 5 exit approval.")
    return {
        "provider": "test_gateway",
        "refund_ref": f"gw_ref_{uuid.uuid4().hex[:16]}",
        "payment_id": payment_id,
        "amount": amount_str,
        "currency": currency,
    }
