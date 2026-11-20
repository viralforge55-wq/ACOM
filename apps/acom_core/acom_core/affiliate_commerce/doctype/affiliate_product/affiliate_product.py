"""Controller for Affiliate Product DocType (DATA_DICTIONARY.md §2).

Invariants enforced here (never bypassed):
- Never links to an ERPNext Item or creates inventory/stock.
- `slug` is derived on insert if blank, lowercase hyphenated, and immutable thereafter.
- `affiliate_url` must be http(s) (never javascript:/data:/etc.) and must contain
  the linked Affiliate Network's `tracking_param` when configured.
- `commission_rate` is within [0, 100]; `commission_type == 'Flat'` requires
  `commission_flat_amount > 0`.
- Publishing (`status == 'Published'`) requires:
  1. `last_verified_date` within 30 days of today (and not in the future)
  2. `content_review_status == 'Approved'`
  3. Linked `Affiliate Network` has `status == 'Active'`
  4. `disclosure_required` is enabled
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlparse

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, getdate, nowdate

from acom_core.affiliate_commerce.doctype.affiliate_network.affiliate_network import (
    SLUG_PATTERN,
    normalize_slug,
)

MAX_PRODUCT_NAME_LEN = 140
MAX_SHORT_DESCRIPTION_LEN = 300
MAX_VERIFICATION_AGE_DAYS = 30
ALLOWED_URL_SCHEMES = frozenset({"http", "https"})


def _validate_http_url(url: str, field_label: str) -> urlparse:
    raw = (url or "").strip()
    if not raw:
        frappe.throw(_("{0} is required.").format(field_label), frappe.ValidationError)

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_URL_SCHEMES or not parsed.netloc:
        frappe.throw(
            _("{0} must be a valid http(s) URL with a host.").format(field_label),
            frappe.ValidationError,
        )
    return parsed


def _to_decimal(value, field_label: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        frappe.throw(_("{0} must be a valid number.").format(field_label), frappe.ValidationError)


class AffiliateProduct(Document):
    def before_validate(self) -> None:
        if self.product_name:
            self.product_name = self.product_name.strip()
        if self.product_sku:
            self.product_sku = self.product_sku.strip()
        if self.affiliate_url:
            self.affiliate_url = self.affiliate_url.strip()
        if self.canonical_url:
            self.canonical_url = self.canonical_url.strip()

        if self.is_new() and not self.slug and self.product_name:
            self.slug = normalize_slug(self.product_name)
        elif self.slug:
            self.slug = self.slug.strip().lower()

        if not self.currency:
            self.currency = "INR"
        if not self.status:
            self.status = "Draft"
        if not self.content_review_status:
            self.content_review_status = "Not Reviewed"

    def validate(self) -> None:
        self._validate_identity()
        self._validate_urls()
        self._validate_commission_and_price()
        self._validate_content_lengths()
        if self.status == "Published":
            self._validate_publish_requirements()

    def _validate_identity(self) -> None:
        if not self.product_name or len(self.product_name) > MAX_PRODUCT_NAME_LEN:
            frappe.throw(
                _("Product Name is required and must be at most {0} characters.").format(
                    MAX_PRODUCT_NAME_LEN
                ),
                frappe.ValidationError,
            )

        if not self.slug or not SLUG_PATTERN.match(self.slug):
            frappe.throw(
                _("Slug must be lowercase alphanumeric with hyphens only."),
                frappe.ValidationError,
            )

        if not self.is_new():
            previous_slug = frappe.db.get_value("Affiliate Product", self.name, "slug")
            if previous_slug and previous_slug != self.slug:
                frappe.throw(
                    _("Slug is immutable after insert. Create a redirect instead of changing it."),
                    frappe.ValidationError,
                )

    def _validate_urls(self) -> None:
        parsed_affiliate = _validate_http_url(self.affiliate_url, "Affiliate URL")

        if self.canonical_url:
            _validate_http_url(self.canonical_url, "Canonical URL")

        if self.affiliate_network:
            tracking_param = frappe.db.get_value(
                "Affiliate Network", self.affiliate_network, "tracking_param"
            )
            if tracking_param:
                qs = parse_qs(parsed_affiliate.query, keep_blank_values=False)
                values = qs.get(tracking_param, [])
                if not any(v.strip() for v in values):
                    frappe.throw(
                        _(
                            "Affiliate URL must include a non-empty '{0}' tracking parameter "
                            "for Affiliate Network '{1}'."
                        ).format(tracking_param, self.affiliate_network),
                        frappe.ValidationError,
                    )

    def _validate_commission_and_price(self) -> None:
        if self.commission_rate is None:
            frappe.throw(_("Commission Rate is required."), frappe.ValidationError)

        rate = _to_decimal(self.commission_rate, "Commission Rate")
        if rate < Decimal("0") or rate > Decimal("100"):
            frappe.throw(
                _("Commission Rate must be between 0 and 100."),
                frappe.ValidationError,
            )

        if self.commission_type == "Flat":
            if self.commission_flat_amount is None:
                frappe.throw(
                    _("Commission Flat Amount is required when Commission Type is Flat."),
                    frappe.ValidationError,
                )
            flat_amt = _to_decimal(self.commission_flat_amount, "Commission Flat Amount")
            if flat_amt <= Decimal("0"):
                frappe.throw(
                    _("Commission Flat Amount must be greater than zero."),
                    frappe.ValidationError,
                )

        if self.display_price is not None and self.display_price != "":
            price = _to_decimal(self.display_price, "Display Price")
            if price < Decimal("0"):
                frappe.throw(_("Display Price cannot be negative."), frappe.ValidationError)

    def _validate_content_lengths(self) -> None:
        if self.short_description and len(self.short_description) > MAX_SHORT_DESCRIPTION_LEN:
            frappe.throw(
                _("Short Description must be at most {0} characters.").format(
                    MAX_SHORT_DESCRIPTION_LEN
                ),
                frappe.ValidationError,
            )

    def _validate_publish_requirements(self) -> None:
        if not self.disclosure_required:
            frappe.throw(
                _("Affiliate disclosure must be enabled before publishing."),
                frappe.ValidationError,
            )

        if self.content_review_status != "Approved":
            frappe.throw(
                _("Cannot publish: Content Review Status must be 'Approved'."),
                frappe.ValidationError,
            )

        if not self.last_verified_date:
            frappe.throw(
                _("Cannot publish: Last Verified Date is required."),
                frappe.ValidationError,
            )

        verified = getdate(self.last_verified_date)
        today = getdate(nowdate())
        age_days = date_diff(today, verified)
        if age_days < 0:
            frappe.throw(
                _("Cannot publish: Last Verified Date cannot be in the future."),
                frappe.ValidationError,
            )
        if age_days > MAX_VERIFICATION_AGE_DAYS:
            frappe.throw(
                _(
                    "Cannot publish: Last Verified Date must be within {0} days "
                    "(currently {1} days old)."
                ).format(MAX_VERIFICATION_AGE_DAYS, age_days),
                frappe.ValidationError,
            )

        network_status = frappe.db.get_value(
            "Affiliate Network", self.affiliate_network, "status"
        )
        if network_status != "Active":
            frappe.throw(
                _(
                    "Cannot publish: linked Affiliate Network '{0}' is '{1}', not Active."
                ).format(self.affiliate_network, network_status or "Missing"),
                frappe.ValidationError,
            )
