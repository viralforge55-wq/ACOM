"""ACOM Core — AI Approval Request DocType Controller.

Governs human-in-the-loop approval workflows, financial firewall role gating,
and mandatory decision auditing per DATA_DICTIONARY §9 and SECURITY_POLICY §7.
"""

from __future__ import annotations

import uuid
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, now_datetime

ALLOWED_ACTION_TYPES = (
    "PublishProduct",
    "SubmitPurchaseOrder",
    "IssueRefund",
    "PriceChange",
    "SupplierOnboarding",
    "ContentPublish",
)

ALLOWED_APPROVAL_STATUSES = (
    "Pending",
    "Approved",
    "Rejected",
    "Expired",
)

ALLOWED_RISK_LEVELS = (
    "Low",
    "Medium",
    "High",
)

HIGH_RISK_ACTIONS = (
    "SubmitPurchaseOrder",
    "IssueRefund",
)

FINANCIAL_APPROVER_ROLES = (
    "System Manager",
    "ACOM Finance",
)

STANDARD_APPROVER_ROLES = (
    "System Manager",
    "ACOM Manager",
    "ACOM Finance",
)


class AIApprovalRequest(Document):
    """DocType controller enforcing human approval boundaries for AI actions."""

    def autoname(self) -> None:
        if not self.request_id:
            self.request_id = str(uuid.uuid4())
        self.name = self.request_id

    def before_validate(self) -> None:
        if not self.request_id:
            self.request_id = str(uuid.uuid4())
        if not self.approval_status:
            self.approval_status = "Pending"
        if not self.expires_at:
            # Default auto-expiration: 72 hours
            self.expires_at = add_to_date(now_datetime(), hours=72)
        if not self.risk_level:
            self.risk_level = "Medium"

        # Automatic escalation to High risk for financial/critical actions
        if self.action_type in HIGH_RISK_ACTIONS or abs(float(self.estimated_financial_impact or 0)) > 5000:
            self.risk_level = "High"

    def validate(self) -> None:
        if self.action_type not in ALLOWED_ACTION_TYPES:
            frappe.throw(
                _("Invalid action_type '{0}'. Must be one of: {1}").format(
                    self.action_type, ", ".join(ALLOWED_ACTION_TYPES)
                ),
                exc=frappe.ValidationError,
            )

        if self.approval_status not in ALLOWED_APPROVAL_STATUSES:
            frappe.throw(
                _("Invalid approval_status '{0}'. Must be one of: {1}").format(
                    self.approval_status, ", ".join(ALLOWED_APPROVAL_STATUSES)
                ),
                exc=frappe.ValidationError,
            )

        if self.risk_level not in ALLOWED_RISK_LEVELS:
            frappe.throw(
                _("Invalid risk_level '{0}'. Must be one of: {1}").format(
                    self.risk_level, ", ".join(ALLOWED_RISK_LEVELS)
                ),
                exc=frappe.ValidationError,
            )

        # Enforce human-in-the-loop security on decision transitions
        user = frappe.session.user if frappe.session else "Guest"
        user_roles = set(frappe.get_roles(user)) if user and user != "Guest" else set()

        # Check for status transitions from previous state
        doc_before_save = self.get_doc_before_save()
        prev_status = doc_before_save.approval_status if doc_before_save else "Pending"

        if self.approval_status == "Approved":
            if user == "Guest":
                frappe.throw(
                    _("Guest sessions cannot approve AI Approval Requests."),
                    exc=frappe.PermissionError,
                )

            # Check expiration
            if self.expires_at and now_datetime() > get_datetime(self.expires_at):
                frappe.throw(
                    _("Cannot approve an expired AI Approval Request (DATA_DICTIONARY §9)."),
                    exc=frappe.ValidationError,
                )

            # Enforce financial firewall (A5): Purchase Orders & Refunds require System Manager or ACOM Finance
            if self.action_type in HIGH_RISK_ACTIONS:
                if not any(role in user_roles for role in FINANCIAL_APPROVER_ROLES):
                    frappe.throw(
                        _(
                            "Approval of '{0}' is restricted to System Manager or ACOM Finance."
                        ).format(self.action_type),
                        exc=frappe.PermissionError,
                    )
            else:
                if not any(role in user_roles for role in STANDARD_APPROVER_ROLES):
                    frappe.throw(
                        _("Insufficient privileges to approve AI Approval Request."),
                        exc=frappe.PermissionError,
                    )

            if not self.approved_by:
                self.approved_by = user
            if not self.approval_timestamp:
                self.approval_timestamp = now_datetime()

        elif self.approval_status == "Rejected":
            if user == "Guest":
                frappe.throw(
                    _("Guest sessions cannot reject AI Approval Requests."),
                    exc=frappe.PermissionError,
                )

            if not any(role in user_roles for role in STANDARD_APPROVER_ROLES):
                frappe.throw(
                    _("Insufficient privileges to reject AI Approval Request."),
                    exc=frappe.PermissionError,
                )

            # Decision note mandatory on rejection per DATA_DICTIONARY §9
            if not self.decision_note or not self.decision_note.strip():
                frappe.throw(
                    _("A decision_note is mandatory when rejecting an AI Approval Request (DATA_DICTIONARY §9)."),
                    exc=frappe.ValidationError,
                )

            if not self.approved_by:
                self.approved_by = user
            if not self.approval_timestamp:
                self.approval_timestamp = now_datetime()

        elif self.approval_status == "Expired":
            if self.expires_at and now_datetime() <= get_datetime(self.expires_at):
                frappe.throw(
                    _("Cannot mark request as Expired before expiration date."),
                    exc=frappe.ValidationError,
                )

    def approve(self, user: str | None = None) -> None:
        """Approve this request."""
        if user:
            self.approved_by = user
        self.approval_status = "Approved"
        self.approval_timestamp = now_datetime()
        self.save()

    def reject(self, decision_note: str, user: str | None = None) -> None:
        """Reject this request with mandatory decision note."""
        if user:
            self.approved_by = user
        self.decision_note = decision_note
        self.approval_status = "Rejected"
        self.approval_timestamp = now_datetime()
        self.save()
