"""Controller for Dropship Checkout DocType (Blueprint §9, W5–W6)."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

import frappe
from frappe import _
from frappe.model.document import Document

PAISA = Decimal("0.01")


class DropshipCheckout(Document):
    def validate(self) -> None:
        if not self.items:
            frappe.throw(_("Dropship Checkout must contain at least one item."), frappe.ValidationError)

        total = Decimal(str(self.grand_total or 0)).quantize(PAISA, rounding=ROUND_HALF_UP)
        if total <= Decimal("0.00"):
            frappe.throw(_("Grand Total must be greater than zero."), frappe.ValidationError)

        if self.refund_amount:
            ref_amt = Decimal(str(self.refund_amount)).quantize(PAISA, rounding=ROUND_HALF_UP)
            if ref_amt < Decimal("0.00") or ref_amt > total:
                frappe.throw(
                    _("Refund Amount must be between 0.00 and Grand Total ({0}).").format(total),
                    frappe.ValidationError,
                )

    def on_trash(self) -> None:
        if not frappe.flags.in_test:
            frappe.throw(
                _("Dropship Checkout records are financial audit records and cannot be deleted."),
                frappe.ValidationError,
            )
