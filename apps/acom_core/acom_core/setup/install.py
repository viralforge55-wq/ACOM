"""Installation and idempotent role bootstrap for acom_core."""

from __future__ import annotations

import frappe

ACOM_ROLES = (
    "ACOM Manager",
    "ACOM Editor",
    "ACOM Finance",
    "ACOM Analyst",
)


def ensure_roles() -> None:
    """Ensure all ACOM custom roles exist. Safe to run repeatedly on migrate."""
    for role_name in ACOM_ROLES:
        if not frappe.db.exists("Role", role_name):
            doc = frappe.get_doc(
                {
                    "doctype": "Role",
                    "role_name": role_name,
                    "desk_access": 1,
                }
            )
            doc.insert(ignore_permissions=True)


def after_install() -> None:
    """Post-install hook: bootstrap roles and default ACOM Settings."""
    ensure_roles()
    settings = frappe.get_single("ACOM Settings")
    if not settings.affiliate_click_retention_days:
        settings.affiliate_click_retention_days = 180
    if settings.return_cost_factor is None or settings.return_cost_factor == 0:
        settings.return_cost_factor = 1.0
    if settings.target_contribution_margin_pct is None:
        settings.target_contribution_margin_pct = 35.0
    if not settings.affiliate_disclosure_text:
        settings.affiliate_disclosure_text = (
            "As an affiliate partner, we may earn a commission from qualifying "
            "purchases made through links on this page, at no extra cost to you."
        )
    settings.save(ignore_permissions=True)
