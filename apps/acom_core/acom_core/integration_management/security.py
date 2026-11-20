"""Machine-to-Machine (M2M) HMAC-SHA256 Security (API_CONTRACTS.md §5, SECURITY_POLICY.md §7).

Enforces:
1. Canonical HMAC-SHA256 signature over raw request bytes:
   HMAC_SHA256(secret, f"{timestamp}.{raw_body}") must match X-ACOM-Signature.
2. Timestamp replay-window: |now - timestamp| <= max_skew_seconds (default 300s).
3. Constant-time signature comparison (hmac.compare_digest).
4. Rejection of missing, expired, tampered, or malformed headers with 401/403.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from functools import wraps
from typing import Any, Callable

import frappe
from acom_core.api.errors import AcomApiError

DEFAULT_MAX_SKEW_SECONDS = 300
DEFAULT_LOCAL_HMAC_SECRET = "acom-m2m-automation-secret-local-phase7-2026"


def get_automation_hmac_secret() -> str:
    """Resolve the M2M automation HMAC secret from site config or env."""
    secret = None
    if hasattr(frappe, "conf") and frappe.conf:
        secret = frappe.conf.get("acom_automation_hmac_secret")
    if not secret:
        secret = os.environ.get("ACOM_AUTOMATION_HMAC_SECRET")
    if not secret:
        # In test mode or local dev fallback to deterministic secret
        secret = DEFAULT_LOCAL_HMAC_SECRET
    return secret


def compute_hmac_signature(raw_body: bytes, secret: str, timestamp: str | int) -> str:
    """Compute HMAC-SHA256 signature matching API_CONTRACTS.md §5."""
    key = secret.encode("utf-8")
    message = f"{timestamp}.".encode("utf-8") + raw_body
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def verify_m2m_signature(
    *,
    raw_body: bytes,
    signature: str | None,
    timestamp: str | None,
    secret: str | None = None,
    max_skew_seconds: int = DEFAULT_MAX_SKEW_SECONDS,
    now_ts: int | None = None,
) -> tuple[bool, str | None]:
    """Verify HMAC signature and timestamp freshness.

    Returns:
        (True, None) on successful verification.
        (False, error_code) on failure.
    """
    clean_sig = (signature or "").strip()
    clean_ts = (timestamp or "").strip()

    if not clean_sig or not clean_ts:
        return False, "MISSING_SIGNATURE_HEADERS"

    try:
        ts_int = int(clean_ts)
    except (ValueError, TypeError):
        return False, "INVALID_TIMESTAMP"

    current_ts = int(time.time()) if now_ts is None else int(now_ts)
    if abs(current_ts - ts_int) > max_skew_seconds:
        return False, "EXPIRED_TIMESTAMP"

    effective_secret = secret or get_automation_hmac_secret()
    expected_sig = compute_hmac_signature(raw_body, effective_secret, clean_ts)

    if not hmac.compare_digest(clean_sig.lower(), expected_sig.lower()):
        return False, "INVALID_SIGNATURE"

    return True, None


def require_m2m_hmac(fn: Callable) -> Callable:
    """Decorator for whitelisted Frappe API methods requiring M2M HMAC authentication."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            req = getattr(frappe.local, "request", None)
            if req is None:
                # Internal direct python call within tests/framework
                if getattr(frappe.flags, "in_test", False) or getattr(frappe.flags, "skip_hmac_for_test", False):
                    return fn(*args, **kwargs)
                raise AcomApiError(
                    "UNAUTHORIZED",
                    "M2M HMAC authentication requires an HTTP request context.",
                    status_code=401,
                )

            # Extract headers
            sig = req.headers.get("X-ACOM-Signature") or req.headers.get("X-Signature")
            ts = req.headers.get("X-ACOM-Timestamp") or req.headers.get("X-Timestamp")

            raw_body = req.get_data(cache=True) or b""

            valid, err_code = verify_m2m_signature(
                raw_body=raw_body,
                signature=sig,
                timestamp=ts,
            )

            if not valid:
                status_code = 401 if err_code in ("MISSING_SIGNATURE_HEADERS", "INVALID_SIGNATURE") else 403
                msg_map = {
                    "MISSING_SIGNATURE_HEADERS": "X-ACOM-Signature and X-ACOM-Timestamp headers are required.",
                    "INVALID_TIMESTAMP": "X-ACOM-Timestamp must be an integer Unix epoch timestamp.",
                    "EXPIRED_TIMESTAMP": f"Timestamp exceeds maximum allowed skew window ({DEFAULT_MAX_SKEW_SECONDS}s).",
                    "INVALID_SIGNATURE": "HMAC signature verification failed.",
                }
                raise AcomApiError(
                    err_code or "UNAUTHORIZED",
                    msg_map.get(err_code or "", "M2M HMAC verification failed."),
                    status_code=status_code,
                )

            return fn(*args, **kwargs)
        except AcomApiError as exc:
            return exc.to_response()

    return wrapper
