"""Controller for Dropshipping Product DocType (DATA_DICTIONARY.md §6).

Invariants enforced on every save:
1. Linked `erpnext_item` and `supplier` must exist and be enabled.
2. `slug` is lowercase hyphenated and immutable after insert.
3. `contribution_profit` and `contribution_margin_pct` are recomputed server-side
   via `product_intelligence.margin.calculate_contribution_profit` (Decimal, GST excluded).
4. Publishing (`status == 'Published'`) requires:
   - `content_review_status == 'Approved'`
   - `contribution_profit >= 0` (negative margin blocks publish)
   - Active ERPNext `Item Price` on `price_list` matches `selling_price` within 0.00 tolerance
   - `supplier_stock > 0`
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

import frappe
from frappe import _
from frappe.model.document import Document

from acom_core.affiliate_commerce.doctype.affiliate_network.affiliate_network import (
    SLUG_PATTERN,
    normalize_slug,
)
from acom_core.product_intelligence.margin import calculate_contribution_profit

PAISA = Decimal("0.01")


def get_active_price_list_rate(item_code: str, price_list: str) -> Decimal | None:
    """Return the active selling Item Price rate for (item_code, price_list) as Decimal."""
    rows = frappe.get_all(
        "Item Price",
        filters={
            "item_code": item_code,
            "price_list": price_list,
            "selling": 1,
        },
        fields=["price_list_rate", "currency", "valid_from", "valid_upto"],
        order_by="modified desc",
        ignore_permissions=True,
    )
    from frappe.utils import getdate, nowdate
    today = getdate(nowdate())
    for row in rows:
        if row.currency != "INR":
            continue
        if row.valid_from and getdate(row.valid_from) > today:
            continue
        if row.valid_upto and getdate(row.valid_upto) < today:
            continue
        return Decimal(str(row.price_list_rate)).quantize(PAISA, rounding=ROUND_HALF_UP)
    return None


class DropshippingProduct(Document):
    def before_validate(self) -> None:
        if self.product_name:
            self.product_name = self.product_name.strip()
        if self.supplier_sku:
            self.supplier_sku = self.supplier_sku.strip()
        if self.hsn_code:
            self.hsn_code = self.hsn_code.strip()

        if self.is_new() and not self.slug and self.product_name:
            self.slug = normalize_slug(self.product_name)
        elif self.slug:
            self.slug = self.slug.strip().lower()

        if not self.currency:
            self.currency = "INR"
        if not self.price_list:
            self.price_list = "Standard Selling"
        if not self.status:
            self.status = "Draft"
        if not self.content_review_status:
            self.content_review_status = "Not Reviewed"

        if not self.category and self.erpnext_item:
            self.category = frappe.db.get_value("Item", self.erpnext_item, "item_group")

        # Pull defaults from ACOM Settings when not specified
        if self.packaging_cost is None:
            self.packaging_cost = frappe.db.get_single_value("ACOM Settings", "packaging_cost_default") or 0
        if self.payment_fee_percent is None:
            self.payment_fee_percent = frappe.db.get_single_value("ACOM Settings", "payment_fee_percent") or 0

    def validate(self) -> None:
        self._validate_identity()
        self._validate_erp_links()
        self._compute_contribution_margin()
        if self.status == "Published":
            self._validate_publish_gates()

    def _validate_identity(self) -> None:
        if not self.slug or not SLUG_PATTERN.match(self.slug):
            frappe.throw(_("Slug must be lowercase alphanumeric with hyphens only."), frappe.ValidationError)
        if not self.is_new():
            prev = frappe.db.get_value("Dropshipping Product", self.name, "slug")
            if prev and prev != self.slug:
                frappe.throw(_("Slug is immutable after insert."), frappe.ValidationError)

        if self.supplier_stock is not None and int(self.supplier_stock) < 0:
            frappe.throw(_("Supplier Stock cannot be negative."), frappe.ValidationError)
        if self.lead_time_days is not None and int(self.lead_time_days) < 0:
            frappe.throw(_("Lead Time Days cannot be negative."), frappe.ValidationError)

    def _validate_erp_links(self) -> None:
        item = frappe.db.get_value("Item", self.erpnext_item, ["name", "disabled"], as_dict=True)
        if not item:
            frappe.throw(_("ERPNext Item '{0}' does not exist.").format(self.erpnext_item), frappe.ValidationError)
        if item.get("disabled"):
            frappe.throw(_("ERPNext Item '{0}' is disabled.").format(self.erpnext_item), frappe.ValidationError)

        sup = frappe.db.get_value("Supplier", self.supplier, ["name", "disabled"], as_dict=True)
        if not sup:
            frappe.throw(_("Supplier '{0}' does not exist.").format(self.supplier), frappe.ValidationError)
        if sup.get("disabled"):
            frappe.throw(_("Supplier '{0}' is disabled.").format(self.supplier), frappe.ValidationError)

    def _compute_contribution_margin(self) -> None:
        return_cost_factor = frappe.db.get_single_value("ACOM Settings", "return_cost_factor") or 1.0
        try:
            result = calculate_contribution_profit(
                selling_price=self.selling_price,
                supplier_cost=self.supplier_cost,
                shipping_cost=self.shipping_cost,
                packaging_cost=self.packaging_cost or 0,
                payment_fee_percent=self.payment_fee_percent or 0,
                expected_return_rate=self.expected_return_rate or 0,
                return_cost_factor=return_cost_factor,
                gst_rate=self.gst_rate or 0,
                currency=self.currency or "INR",
            )
        except ValueError as exc:
            frappe.throw(str(exc), frappe.ValidationError)

        self.contribution_profit = float(result.contribution_profit)
        self.contribution_margin_pct = float(result.contribution_margin_pct)

    def _validate_publish_gates(self) -> None:
        if self.content_review_status != "Approved":
            frappe.throw(
                _("Cannot publish: Content Review Status must be 'Approved'."),
                frappe.ValidationError,
            )

        profit = Decimal(str(self.contribution_profit or 0)).quantize(PAISA, rounding=ROUND_HALF_UP)
        if profit < Decimal("0.00"):
            frappe.throw(
                _("Cannot publish: negative contribution profit ({0}).").format(profit),
                frappe.ValidationError,
            )

        if int(self.supplier_stock or 0) <= 0:
            frappe.throw(
                _("Cannot publish: supplier stock must be greater than zero."),
                frappe.ValidationError,
            )

        active_rate = get_active_price_list_rate(self.erpnext_item, self.price_list)
        if active_rate is None:
            frappe.throw(
                _("Cannot publish: no active selling Item Price found for '{0}' in Price List '{1}'.").format(
                    self.erpnext_item, self.price_list
                ),
                frappe.ValidationError,
            )
        declared = Decimal(str(self.selling_price)).quantize(PAISA, rounding=ROUND_HALF_UP)
        if declared != active_rate:
            frappe.throw(
                _("Cannot publish: selling_price ({0}) does not match active Price List rate ({1}).").format(
                    declared, active_rate
                ),
                frappe.ValidationError,
            )
