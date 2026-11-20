"""Controller for ACOM Settings (Single DocType)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class ACOMSettings(Document):
    def validate(self) -> None:
        if self.payment_fee_percent is not None and not (0 <= float(self.payment_fee_percent) <= 100):
            frappe.throw(_("Payment Fee Percent must be between 0 and 100."))
        if self.return_cost_factor is not None and float(self.return_cost_factor) < 0:
            frappe.throw(_("Return Cost Factor cannot be negative."))
        if (
            self.affiliate_click_retention_days is not None
            and int(self.affiliate_click_retention_days) < 1
        ):
            frappe.throw(_("Affiliate Click Retention Days must be at least 1."))
        if self.ai_max_retries is not None and int(self.ai_max_retries) < 0:
            frappe.throw(_("AI Max Retries cannot be negative."))
        if self.ai_task_timeout_seconds is not None and int(self.ai_task_timeout_seconds) < 1:
            frappe.throw(_("AI Task Timeout Seconds must be at least 1."))
