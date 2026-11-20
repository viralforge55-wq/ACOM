"""Controller for Affiliate Import Batch DocType (DATA_DICTIONARY.md §4 & W4)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class AffiliateImportBatch(Document):
    def before_insert(self) -> None:
        self.imported_at = now_datetime()
        if not self.imported_by:
            self.imported_by = frappe.session.user

    def on_trash(self) -> None:
        if not frappe.flags.in_test:
            frappe.throw(
                _("Affiliate Import Batch records are audit history and cannot be deleted."),
                frappe.ValidationError,
            )
