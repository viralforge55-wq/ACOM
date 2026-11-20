"""Controller for Affiliate Network DocType (DATA_DICTIONARY.md §5)."""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PARAM_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def normalize_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return slug


class AffiliateNetwork(Document):
    def before_validate(self) -> None:
        if self.network_name:
            self.network_name = self.network_name.strip()
        if not self.slug and self.network_name:
            self.slug = normalize_slug(self.network_name)
        elif self.slug:
            self.slug = self.slug.strip().lower()
        if self.tracking_param:
            self.tracking_param = self.tracking_param.strip()

    def validate(self) -> None:
        if not self.slug or not SLUG_PATTERN.match(self.slug):
            frappe.throw(
                _("Slug must be lowercase alphanumeric with hyphens only (e.g. 'amazon-in')."),
                frappe.ValidationError,
            )

        if not self.is_new():
            previous_slug = frappe.db.get_value("Affiliate Network", self.name, "slug")
            if previous_slug and previous_slug != self.slug:
                frappe.throw(
                    _("Slug is immutable after insert."),
                    frappe.ValidationError,
                )

        if self.cookie_window_days is not None and int(self.cookie_window_days) < 0:
            frappe.throw(
                _("Cookie Window Days cannot be negative."),
                frappe.ValidationError,
            )

        if self.tracking_param and not PARAM_PATTERN.match(self.tracking_param):
            frappe.throw(
                _("Tracking Parameter must contain only letters, digits, hyphens, or underscores."),
                frappe.ValidationError,
            )
