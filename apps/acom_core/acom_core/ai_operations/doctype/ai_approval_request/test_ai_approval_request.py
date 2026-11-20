"""Unit & Integration tests for AI Approval Request (DATA_DICTIONARY §9, SECURITY_POLICY §7, TEST_PLAN A4, A5, X6)."""

from __future__ import annotations

import unittest
import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from acom_core.ai_operations.doctype.ai_approval_request.ai_approval_request import (
    AIApprovalRequest,
)
from acom_core.ai_operations.services.approval_service import (
    create_approval_request,
    decide_approval_request,
)

IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Fiscal Year", "Item", "Currency", "User", "DocType"]


class TestAIApprovalRequest(IntegrationTestCase):
    """Test AI Approval Request governance, human-in-the-loop gating, and A5 financial firewall."""

    def setUp(self) -> None:
        frappe.set_user("Administrator")
        # Ensure test users exist
        self._ensure_test_user("test_editor@acom.local", "ACOM Editor")
        self._ensure_test_user("test_manager@acom.local", "ACOM Manager")
        self._ensure_test_user("test_finance@acom.local", "ACOM Finance")

    def tearDown(self) -> None:
        frappe.set_user("Administrator")

    def _ensure_test_user(self, email: str, role: str) -> None:
        if not frappe.db.exists("User", email):
            u = frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": email.split("@")[0],
                    "enabled": 1,
                    "roles": [{"doctype": "Has Role", "role": role}],
                }
            )
            u.insert(ignore_permissions=True)
        else:
            u = frappe.get_doc("User", email)
            if not any(r.role == role for r in u.roles):
                u.append("roles", {"role": role})
                u.save(ignore_permissions=True)

    def test_risk_escalation_for_financial_actions(self) -> None:
        """Purchase Orders, Refunds, or high financial impact are automatically escalated to High risk."""
        req1 = create_approval_request(
            action_type="SubmitPurchaseOrder",
            related_doctype="Purchase Order",
            related_name="PO-DRAFT-001",
            recommendation="Submit draft purchase order to supplier",
        )
        doc1 = frappe.get_doc("AI Approval Request", req1["request_id"])
        self.assertEqual(doc1.risk_level, "High")

        req2 = create_approval_request(
            action_type="PublishProduct",
            related_doctype="Dropshipping Product",
            related_name="DPROD-001",
            recommendation="Publish candidate product",
            estimated_financial_impact=10000.0,
        )
        doc2 = frappe.get_doc("AI Approval Request", req2["request_id"])
        self.assertEqual(doc2.risk_level, "High")

    def test_A4_guest_cannot_approve_or_reject(self) -> None:
        """Guest sessions receive PermissionError on any approval or rejection attempt."""
        req = create_approval_request(
            action_type="PublishProduct",
            related_doctype="Dropshipping Product",
            related_name="DPROD-TEST",
            recommendation="Publish product",
        )
        request_id = req["request_id"]

        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            decide_approval_request(request_id, "Approved")

        with self.assertRaises(frappe.PermissionError):
            decide_approval_request(request_id, "Rejected", decision_note="Bad product")

    def test_A5_X6_financial_firewall_blocks_manager_on_po_submission(self) -> None:
        """PO submission approval is strictly restricted to System Manager or ACOM Finance.
        ACOM Manager or Editor is blocked with PermissionError.
        """
        req = create_approval_request(
            action_type="SubmitPurchaseOrder",
            related_doctype="Purchase Order",
            related_name="PO-TEST-001",
            recommendation="Submit PO",
            estimated_financial_impact=-15000.0,
        )
        request_id = req["request_id"]

        # Attempt as ACOM Manager
        frappe.set_user("test_manager@acom.local")
        with self.assertRaises(frappe.PermissionError):
            decide_approval_request(request_id, "Approved")

        # Attempt as ACOM Finance (allowed)
        frappe.set_user("test_finance@acom.local")
        res = decide_approval_request(request_id, "Approved")
        self.assertTrue(res["ok"])
        self.assertEqual(res["approval_status"], "Approved")

    def test_decision_note_mandatory_on_rejection(self) -> None:
        """Rejection without a decision note raises ValidationError per DATA_DICTIONARY §9."""
        req = create_approval_request(
            action_type="PublishProduct",
            related_doctype="Dropshipping Product",
            related_name="DPROD-TEST",
            recommendation="Publish product",
        )
        request_id = req["request_id"]

        frappe.set_user("test_manager@acom.local")
        # Empty note fails
        res = decide_approval_request(request_id, "Rejected", decision_note="")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error_code"], "VALIDATION_ERROR")

        # Non-empty note succeeds
        res_ok = decide_approval_request(request_id, "Rejected", decision_note="Margin below target")
        self.assertTrue(res_ok["ok"])
        self.assertEqual(res_ok["approval_status"], "Rejected")

    def test_expired_approval_request_cannot_be_approved(self) -> None:
        """Expired requests cannot be retroactively approved (DATA_DICTIONARY §9)."""
        req = create_approval_request(
            action_type="PublishProduct",
            related_doctype="Dropshipping Product",
            related_name="DPROD-EXP",
            recommendation="Publish product",
        )
        request_id = req["request_id"]
        doc = frappe.get_doc("AI Approval Request", request_id)
        # Set expiration to the past
        doc.expires_at = add_to_date(now_datetime(), hours=-2)
        doc.save(ignore_permissions=True)

        frappe.set_user("Administrator")
        with self.assertRaises(frappe.ValidationError):
            doc.approve()
