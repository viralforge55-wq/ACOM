"""Protected Business Intelligence & CEO Dashboard API endpoints (Phase 8).

Routes via Frappe (strictly authenticated + role-checked; Guest gets HTTP 401, non-managers get 403):
- GET /api/method/acom_core.api.dashboard.get_ceo_dashboard_summary
- GET /api/method/acom_core.api.dashboard.get_product_profitability
- GET /api/method/acom_core.api.dashboard.get_drill_through
"""

from __future__ import annotations

import json
from typing import Any

import frappe

from acom_core.analytics.services.ceo_dashboard_service import (
    get_ceo_dashboard_summary as _get_summary,
    get_drill_through_records as _get_drill_records,
)
from acom_core.analytics.services.profitability_service import (
    get_product_profitability_report as _get_profit_report,
)
from acom_core.api.errors import AcomApiError, error_response, ok_response


DASHBOARD_ROLES = (
    "System Manager",
    "ACOM Manager",
    "ACOM Finance",
)

BANNED_EXECUTIVE_SECRETS = frozenset({
    "password",
    "api_secret",
    "secret",
    "card_number",
    "cvv",
    "auth_token",
    "private_key",
    "raw_key",
})


def assert_no_executive_leaks(obj: Any, path: str = "$") -> None:
    """Verify that credentials and secrets never leak in dashboard API responses."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in BANNED_EXECUTIVE_SECRETS:
                frappe.log_error(
                    title="ACOM security guard blocked secret in dashboard",
                    message=f"Blocked secret key '{key}' at {path}",
                )
                raise AcomApiError(
                    "INTERNAL_ERROR",
                    "Security violation: secret leaked in dashboard API.",
                    status_code=500,
                )
            assert_no_executive_leaks(value, f"{path}.{key}")
    elif isinstance(obj, (list, tuple)):
        for idx, item in enumerate(obj):
            assert_no_executive_leaks(item, f"{path}[{idx}]")


def _check_authenticated_role(allowed_roles: tuple[str, ...] = DASHBOARD_ROLES) -> None:
    """Ensure session is not Guest and user holds an executive/management role."""
    user = frappe.session.user if frappe.session else "Guest"
    if not user or user == "Guest":
        raise AcomApiError("UNAUTHENTICATED", "Authentication required.", status_code=401)

    roles = set(frappe.get_roles(user))
    if not any(r in roles for r in allowed_roles):
        raise AcomApiError("FORBIDDEN", "Insufficient privileges for executive dashboard.", status_code=403)


@frappe.whitelist(methods=["GET"])
def get_ceo_dashboard_summary(
    period: str | None = "today",
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Retrieve consolidated Daily CEO Dashboard metrics with drill-through maps."""
    try:
        _check_authenticated_role(DASHBOARD_ROLES)
        if period not in ("today", "all_time", "custom"):
            period = "today"

        data = _get_summary(period=period, date_from=date_from, date_to=date_to)
        assert_no_executive_leaks(data)
        return ok_response(data, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM get_ceo_dashboard_summary unexpected error")
        return error_response("INTERNAL_ERROR", "An unexpected error occurred while compiling dashboard.", status_code=500)


@frappe.whitelist(methods=["GET"])
def get_product_profitability(
    channel: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | str = 100,
) -> dict[str, Any]:
    """Retrieve ranked product profitability and unit economics."""
    try:
        _check_authenticated_role(DASHBOARD_ROLES)
        try:
            lim = int(limit)
        except (ValueError, TypeError):
            lim = 100

        data = _get_profit_report(channel=channel, date_from=date_from, date_to=date_to, limit=lim)
        assert_no_executive_leaks(data)
        return ok_response(data, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM get_product_profitability unexpected error")
        return error_response("INTERNAL_ERROR", "An unexpected error occurred while compiling profitability.", status_code=500)


@frappe.whitelist(methods=["GET"])
def get_drill_through(
    metric_key: str | None = None,
    limit: int | str = 50,
) -> dict[str, Any]:
    """Retrieve underlying transaction rows for drill-through auditing (TEST_PLAN Gate 8)."""
    try:
        _check_authenticated_role(DASHBOARD_ROLES)
        if not metric_key:
            raise AcomApiError("VALIDATION_ERROR", "metric_key parameter is required.", status_code=400)

        try:
            lim = int(limit)
        except (ValueError, TypeError):
            lim = 50

        records = _get_drill_records(metric_key=str(metric_key), limit=lim)
        assert_no_executive_leaks(records)
        return ok_response({"metric_key": metric_key, "count": len(records), "records": records}, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM get_drill_through unexpected error")
        return error_response("INTERNAL_ERROR", "An unexpected error occurred while fetching drill-through records.", status_code=500)
