"""Affiliate click and management API endpoints (API_CONTRACTS.md §2).

Routes via Frappe:
- POST /api/method/acom_core.api.affiliate.record_affiliate_click
- GET  /api/method/acom_core.api.affiliate.resolve_affiliate_redirect
- POST /api/method/acom_core.api.affiliate.update_affiliate_product_status (authenticated)
"""

from __future__ import annotations

import json
from typing import Any

import frappe

from acom_core.affiliate_commerce.services.click_service import (
    record_click,
    resolve_redirect,
)
from acom_core.affiliate_commerce.services.product_service import (
    set_affiliate_product_status,
)
from acom_core.api.errors import AcomApiError, error_response, ok_response

_FRAPPE_INTERNAL_PARAMS = frozenset({"cmd", "_"})


def _extract_json_body(explicit_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Extract request body cleanly for both HTTP JSON POSTs and direct Python calls."""
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


def _extract_request_metadata() -> tuple[str | None, str | None]:
    """Read User-Agent and client IP from HTTP request without persisting either raw."""
    request = getattr(frappe.local, "request", None)
    if request is None:
        return (None, None)
    user_agent = request.headers.get("User-Agent")
    client_ip = getattr(frappe.local, "request_ip", None) or request.remote_addr
    return (user_agent, client_ip)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def record_affiliate_click(
    product_slug: str | None = None,
    session_id: str | None = None,
    source: str | None = None,
    medium: str | None = None,
    referrer: str | None = None,
    landing_path: str | None = None,
    clicked_at: str | None = None,
) -> dict[str, Any]:
    """Record an anonymous affiliate click (maps to POST /api/affiliate/click).

    Append-only telemetry with zero PII, strict schema validation, rate limiting,
    and 2-second deduplication. Never mutates business truth or creates revenue.
    """
    try:
        payload = _extract_json_body(
            {
                "product_slug": product_slug,
                "session_id": session_id,
                "source": source,
                "medium": medium,
                "referrer": referrer,
                "landing_path": landing_path,
                "clicked_at": clicked_at,
            }
        )
        user_agent, client_ip = _extract_request_metadata()
        data, status_code = record_click(
            payload,
            user_agent=user_agent,
            client_ip=client_ip,
        )
        return ok_response(data, status_code=status_code)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM record_affiliate_click unexpected error")
        return error_response(
            "INTERNAL_ERROR",
            "An unexpected error occurred.",
            status_code=500,
        )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def resolve_affiliate_redirect(click_id: str = "") -> dict[str, Any]:
    """Resolve a click_id into the outbound affiliate URL with sub-ID parameter."""
    try:
        data = resolve_redirect(click_id=click_id)
        return ok_response(data, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM resolve_affiliate_redirect unexpected error")
        return error_response(
            "INTERNAL_ERROR",
            "An unexpected error occurred.",
            status_code=500,
        )


@frappe.whitelist(allow_guest=False, methods=["POST"])
def update_affiliate_product_status(
    product_name: str = "",
    status: str = "",
) -> dict[str, Any]:
    """Authenticated, role-checked business mutation for Affiliate Product status.

    Requires System Manager or ACOM Manager role (SECURITY_POLICY.md §4, gate G3).
    """
    try:
        data = set_affiliate_product_status(product_name=product_name, status=status)
        return ok_response(data, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM update_affiliate_product_status unexpected error")
        return error_response(
            "INTERNAL_ERROR",
            "An unexpected error occurred.",
            status_code=500,
        )
