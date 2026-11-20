"""Public read-only catalog API endpoints (API_CONTRACTS.md §1).

Routes via Frappe:
- GET /api/method/acom_core.api.catalog.get_catalog
- GET /api/method/acom_core.api.catalog.get_product
- GET /api/method/acom_core.api.catalog.get_categories
"""

from __future__ import annotations

from typing import Any

import frappe

from acom_core.affiliate_commerce.services.catalog_service import (
    get_public_product_by_slug,
    list_public_catalog,
    list_public_categories,
)
from acom_core.api.errors import AcomApiError, error_response, ok_response

# Keys Frappe injects into form_dict on HTTP requests
_FRAPPE_INTERNAL_PARAMS = frozenset({"cmd", "_"})


def _reject_unknown_query_params(allowed: frozenset[str]) -> None:
    form = getattr(frappe.local, "form_dict", None)
    if not form:
        return
    unknown = sorted(
        k for k in form.keys() if k not in allowed and k not in _FRAPPE_INTERNAL_PARAMS
    )
    if unknown:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Unknown query parameters are not permitted.",
            status_code=400,
            details={"fields": unknown},
        )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_catalog(
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    sales_type: str | None = None,
    sort: str = "newest",
    q: str | None = None,
) -> dict[str, Any]:
    """Public read-only catalog listing (maps to GET /api/catalog)."""
    try:
        _reject_unknown_query_params(
            frozenset({"page", "page_size", "category", "sales_type", "sort", "q"})
        )
        data, meta = list_public_catalog(
            page=page,
            page_size=page_size,
            category=category,
            sales_type=sales_type,
            sort=sort,
            q=q,
        )
        return ok_response(data, meta=meta, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM get_catalog unexpected error")
        return error_response(
            "INTERNAL_ERROR",
            "An unexpected error occurred.",
            status_code=500,
        )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_product(slug: str = "") -> dict[str, Any]:
    """Public read-only single product detail (maps to GET /api/products/{slug})."""
    try:
        _reject_unknown_query_params(frozenset({"slug"}))
        product = get_public_product_by_slug(slug=slug)
        return ok_response(product, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM get_product unexpected error")
        return error_response(
            "INTERNAL_ERROR",
            "An unexpected error occurred.",
            status_code=500,
        )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_categories() -> dict[str, Any]:
    """Public read-only categories list (maps to GET /api/categories)."""
    try:
        _reject_unknown_query_params(frozenset())
        data = list_public_categories()
        return ok_response(data, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception:
        frappe.log_error(title="ACOM get_categories unexpected error")
        return error_response(
            "INTERNAL_ERROR",
            "An unexpected error occurred.",
            status_code=500,
        )
