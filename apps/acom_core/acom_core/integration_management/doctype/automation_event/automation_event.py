"""Controller for Automation Event outbox DocType (DATA_DICTIONARY.md §10)."""

from __future__ import annotations

import uuid

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class AutomationEvent(Document):
    def before_insert(self) -> None:
        if not self.event_id:
            self.event_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = now_datetime()
        if not self.processing_status:
            self.processing_status = "Received"
        if self.retry_count is None:
            self.retry_count = 0

    def on_trash(self) -> None:
        if not (frappe.flags.in_test or frappe.flags.get("acom_retention_purge")):
            frappe.throw(
                _("Automation Event outbox records cannot be deleted manually."),
                frappe.ValidationError,
            )
