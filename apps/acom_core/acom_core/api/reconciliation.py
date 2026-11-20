"""Protected Affiliate Conversion Import & Reconciliation API endpoints (Phase 4).

Routes via Frappe (all strictly authenticated + role-checked; Guest gets HTTP 403):
- POST /api/method/acom_core.api.reconciliation.import_affiliate_report
- GET  /api/method/acom_core.api.reconciliation.get_affiliate_reconciliation
- POST /api/method/acom_core.api.reconciliation.resolve_orphan_conversion
"""

from __future__ import annotations

import json
from typing import Any

import frappe

from acom_core.affiliate_commerce.services.conversion_service import (
    import_affiliate_conversions,
)
from acom_core.affiliate_commerce.services.reconciliation_service import (
    get_reconciliation_summary,
    resolve_unmatched_conversion,
)
from acom_core.api.errors import AcomApiError, error_response, ok_response

_FRAPPE_INTERNAL_PARAMS = frozenset({"cmd", "_"})


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


@frappe.whitelist(allow_guest=False, methods=["POST"])
def import_affiliate_report(
    network: str | None = None,
    report_date: str | None = None,
    rows: list[dict[str, Any]] | str | None = None,
    csv_content: str | None = None,
    file_name: str | None = None,
) -> dict[str, Any]:
    """Protected endpoint for idempotent affiliate conversion import (API_CONTRACTS.md §5)."""
    try:
        body = _extract_json_body(
            {
                "network": network,
                "report_date": report_date,
                "rows": rows,
                "csv_content": csv_content,
                "file_name": file_name,
            }
        )
        allowed_keys = {"network", "report_date", "rows", "csv_content", "file_name"}
        unknown = sorted(k for k in body.keys() if k not in allowed_keys)
        if unknown:
            raise AcomApiError(
                "VALIDATION_ERROR",
                "Unknown fields in import payload.",
                status_code=400,
                details={"fields": unknown},
            )

        parsed_rows = body.get("rows")
        if isinstance(parsed_rows, str):
            try:
                parsed_rows = json.loads(parsed_rows)
            except json.JSONDecodeError as exc:
                raise AcomApiError(
                    "VALIDATION_ERROR",
                    "rows must be a JSON array.",
                    status_code=400,
                    details={"fields": ["rows"]},
                ) from exc

        result = import_affiliate_conversions(
            network=str(body.get("network") or ""),
            report_date=str(body.get("report_date") or ""),
            rows=parsed_rows,
            csv_content=body.get("csv_content"),
            file_name=body.get("file_name"),
        )
        return ok_response(result, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except frappe.ValidationError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=422)
    except Exception:
        frappe.log_error(title="ACOM import_affiliate_report unexpected error")
        return error_response("INTERNAL_ERROR", "An unexpected error occurred.", status_code=500)


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_affiliate_reconciliation(
    affiliate_network: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    payout_expected: str | None = None,
    currency: str = "INR",
) -> dict[str, Any]:
    """Protected endpoint returning click attribution and commission reconciliation summary."""
    try:
        data = get_reconciliation_summary(
            affiliate_network=affiliate_network,
            date_from=date_from,
            date_to=date_to,
            payout_expected=payout_expected,
            currency=currency,
        )
        return ok_response(data, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM get_affiliate_reconciliation unexpected error")
        return error_response("INTERNAL_ERROR", "An unexpected error occurred.", status_code=500)


@frappe.whitelist(allow_guest=False, methods=["POST"])
def resolve_orphan_conversion(
    conversion_name: str | None = None,
    affiliate_product: str | None = None,
    affiliate_click: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Protected endpoint to manually attribute an orphan Affiliate Conversion."""
    try:
        body = _extract_json_body(
            {
                "conversion_name": conversion_name,
                "affiliate_product": affiliate_product,
                "affiliate_click": affiliate_click,
                "note": note,
            }
        )
        result = resolve_unmatched_conversion(
            conversion_name=str(body.get("conversion_name") or ""),
            affiliate_product=body.get("affiliate_product"),
            affiliate_click=body.get("affiliate_click"),
            note=str(body.get("note") or ""),
        )
        return ok_response(result, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except frappe.ValidationError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=422)
    except Exception:
        frappe.log_error(title="ACOM resolve_orphan_conversion unexpected error")
        return error_response("INTERNAL_ERROR", "An unexpected error occurred.", status_code=500)
