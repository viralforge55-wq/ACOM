"""Controller for Supplier Performance DocType (DATA_DICTIONARY.md §7)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from acom_core.product_intelligence.scoring import calculate_supplier_reliability


class SupplierPerformance(Document):
    def before_validate(self) -> None:
        if self.supplier and self.period_start and self.period_end:
            self.period_key = f"{self.supplier}::{self.period_start}::{self.period_end}"

    def validate(self) -> None:
        if self.period_start and self.period_end and getdate(self.period_end) < getdate(self.period_start):
            frappe.throw(_("Period End cannot be earlier than Period Start."), frappe.ValidationError)

        try:
            res = calculate_supplier_reliability(
                orders_received=int(self.orders_received or 0),
                orders_fulfilled=int(self.orders_fulfilled or 0),
                orders_cancelled=int(self.orders_cancelled or 0),
                orders_returned=int(self.orders_returned or 0),
                avg_dispatch_hours=self.avg_dispatch_hours,
                quality_issues=int(self.quality_issues or 0),
            )
        except ValueError as exc:
            frappe.throw(str(exc), frappe.ValidationError)

        self.cancellation_rate = float(res.cancellation_rate)
        self.return_rate = float(res.return_rate)
        self.reliability_score = float(res.reliability_score)
