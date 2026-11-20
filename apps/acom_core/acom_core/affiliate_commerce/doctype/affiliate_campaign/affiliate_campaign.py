"""Controller for Affiliate Campaign DocType."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from acom_core.affiliate_commerce.doctype.affiliate_network.affiliate_network import (
    SLUG_PATTERN,
    normalize_slug,
)


class AffiliateCampaign(Document):
    def before_validate(self) -> None:
        if self.campaign_name:
            self.campaign_name = self.campaign_name.strip()
        if not self.slug and self.campaign_name:
            self.slug = normalize_slug(self.campaign_name)
        elif self.slug:
            self.slug = self.slug.strip().lower()

    def validate(self) -> None:
        if not self.slug or not SLUG_PATTERN.match(self.slug):
            frappe.throw(
                _("Slug must be lowercase alphanumeric with hyphens only."),
                frappe.ValidationError,
            )

        if not self.is_new():
            previous_slug = frappe.db.get_value("Affiliate Campaign", self.name, "slug")
            if previous_slug and previous_slug != self.slug:
                frappe.throw(_("Slug is immutable after insert."), frappe.ValidationError)

        if self.start_date and self.end_date and getdate(self.end_date) < getdate(self.start_date):
            frappe.throw(
                _("End Date cannot be earlier than Start Date."),
                frappe.ValidationError,
            )
