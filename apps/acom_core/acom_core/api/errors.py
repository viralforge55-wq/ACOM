"""Shared API envelope, correlation ID, and error handling (API_CONTRACTS.md §0 & §7)."""

from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import frappe

PAISA = Decimal("0.01")


def get_correlation_id() -> str:
    """Return request-scoped correlation ID, creating one if absent."""
    cid = getattr(frappe.local, "acom_correlation_id", None)
    if not cid:
        header_cid = None
        if getattr(frappe.local, "request", None) is not None:
            header_cid = frappe.local.request.headers.get("X-Correlation-Id")
        if header_cid and len(header_cid) <= 64 and header_cid.replace("-", "").isalnum():
            cid = header_cid
        else:
            cid = str(uuid.uuid4())
        frappe.local.acom_correlation_id = cid
    return cid


def format_money(amount, currency: str = "INR") -> dict[str, str]:
    """Format a monetary amount as string decimal + 3-letter ISO currency."""
    dec = Decimal(str(amount)).quantize(PAISA, rounding=ROUND_HALF_UP)
    return {
        "amount": f"{dec:.2f}",
        "currency": (currency or "INR").upper(),
    }


def _set_http_status(status_code: int, headers: dict[str, str] | None = None) -> None:
    if hasattr(frappe.local, "response") and isinstance(frappe.local.response, dict):
        frappe.local.response["http_status_code"] = status_code
        if headers:
            resp_headers = frappe.local.response.setdefault("headers", {})
            resp_headers.update(headers)


def ok_response(
    data: dict[str, Any],
    *,
    meta: dict[str, Any] | None = None,
    status_code: int = 200,
) -> dict[str, Any]:
    """Build standard success envelope per API_CONTRACTS.md §0.1."""
    _set_http_status(status_code)
    merged_meta: dict[str, Any] = dict(meta or {})
    merged_meta["correlation_id"] = get_correlation_id()
    return {
        "ok": True,
        "data": data,
        "meta": merged_meta,
    }


def error_response(
    code: str,
    message: str,
    *,
    status_code: int = 400,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build standard failure envelope per API_CONTRACTS.md §0.1.

    Never leaks tracebacks or secrets.
    """
    _set_http_status(status_code, headers=headers)
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
        "meta": {
            "correlation_id": get_correlation_id(),
        },
    }


class AcomApiError(Exception):
    """Structured domain/API error mapped cleanly to API_CONTRACTS.md §7."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.headers = headers or {}

    def to_response(self) -> dict[str, Any]:
        return error_response(
            self.code,
            self.message,
            status_code=self.status_code,
            details=self.details,
            headers=self.headers,
        )
