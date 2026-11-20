"""Authenticated management service for Affiliate Product status transitions."""

from __future__ import annotations

from typing import Any

import frappe

from acom_core.api.errors import AcomApiError

ALLOWED_PRODUCT_STATUSES = frozenset(
    {
        "Draft",
        "Pending Approval",
        "Published",
        "Paused",
        "Rejected",
        "Expired",
    }
)

PRIVILEGED_ROLES = ("System Manager", "ACOM Manager")


def set_affiliate_product_status(*, product_name: str, status: str) -> dict[str, Any]:
    """Change an Affiliate Product's status with explicit role and controller validation."""
    if frappe.session.user == "Guest":
        raise AcomApiError("UNAUTHENTICATED", "Authentication required.", status_code=401)

    user_roles = set(frappe.get_roles(frappe.session.user))
    if not user_roles.intersection(PRIVILEGED_ROLES):
        raise AcomApiError("FORBIDDEN", "Not permitted.", status_code=403)

    cleaned_name = (product_name or "").strip()
    cleaned_status = (status or "").strip()
    if not cleaned_name:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "product_name is required.",
            status_code=400,
            details={"fields": ["product_name"]},
        )
    if cleaned_status not in ALLOWED_PRODUCT_STATUSES:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Invalid Affiliate Product status.",
            status_code=400,
            details={"fields": ["status"]},
        )

    if not frappe.db.exists("Affiliate Product", cleaned_name):
        raise AcomApiError("NOT_FOUND", "Affiliate product not found.", status_code=404)

    doc = frappe.get_doc("Affiliate Product", cleaned_name)
    doc.status = cleaned_status
    try:
        doc.save()
    except frappe.ValidationError as exc:
        raise AcomApiError(
            "VALIDATION_ERROR",
            str(exc),
            status_code=422,
            details={"product_name": cleaned_name, "status": cleaned_status},
        ) from exc

    return {
        "id": doc.name,
        "slug": doc.slug,
        "status": doc.status,
    }
