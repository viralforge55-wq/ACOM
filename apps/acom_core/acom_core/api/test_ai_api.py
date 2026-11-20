"""Integration tests for AI Operations internal APIs (API_CONTRACTS.md §5, §7)."""

from __future__ import annotations

import json
import unittest
import frappe
from frappe.tests import IntegrationTestCase

from acom_core.api.ai import (
    create_approval,
    create_task,
    decide_approval,
    get_task_status,
    submit_result,
)


class TestAIOperationsAPI(IntegrationTestCase):
    """Test AI API role gating, schema rejection, and A5 financial firewall."""

    def setUp(self) -> None:
        frappe.set_user("Administrator")
        self._ensure_user("api_editor@acom.local", "ACOM Editor")
        self._ensure_user("api_manager@acom.local", "ACOM Manager")
        self._ensure_user("api_finance@acom.local", "ACOM Finance")

    def tearDown(self) -> None:
        frappe.set_user("Administrator")

    def _ensure_user(self, email: str, role: str) -> None:
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

    def test_guest_rejected_on_all_ai_endpoints(self) -> None:
        """Guest cannot access any AI API endpoint (API_CONTRACTS §5)."""
        frappe.set_user("Guest")

        # create_task
        res1 = create_task("ProductResearch", "product_hunter", "qwen2.5:3b")
        self.assertFalse(res1["ok"])
        self.assertEqual(res1["error"]["code"], "UNAUTHENTICATED")

        # submit_result
        res2 = submit_result("dummy-task-id", {})
        self.assertFalse(res2["ok"])
        self.assertEqual(res2["error"]["code"], "UNAUTHENTICATED")

        # get_task_status
        res3 = get_task_status("dummy-task-id")
        self.assertFalse(res3["ok"])
        self.assertEqual(res3["error"]["code"], "UNAUTHENTICATED")

        # decide_approval
        res4 = decide_approval("dummy-req-id", "Approved")
        self.assertFalse(res4["ok"])
        self.assertEqual(res4["error"]["code"], "UNAUTHENTICATED")

    def test_schema_invalid_returns_422(self) -> None:
        """Invalid schema output rejected with 422 SCHEMA_INVALID (API_CONTRACTS §5)."""
        frappe.set_user("api_editor@acom.local")
        t_res = create_task(
            task_type="ProductResearch",
            agent_id="product_hunter",
            model="qwen2.5:3b",
            input_payload={"sku": "TEST-422"},
        )
        task_id = t_res["data"]["task_id"]

        bad_output = {"only_one_field": "test"}
        res = submit_result(task_id, bad_output)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "SCHEMA_INVALID")

    def test_valid_schema_submission_succeeds(self) -> None:
        """Valid schema output marks task Succeeded and returns 200."""
        frappe.set_user("api_editor@acom.local")
        t_res = create_task(
            task_type="ProductResearch",
            agent_id="product_hunter",
            model="qwen2.5:3b",
            input_payload={"sku": "TEST-OK-01"},
        )
        task_id = t_res["data"]["task_id"]

        valid_output = {
            "product_name": "Bamboo Cutlery Set",
            "category": "Kitchen",
            "supplier_name": "EcoSupplier",
            "supplier_sku": "ECO-BAM-01",
            "supplier_price": "250.00",
            "competitor_price": "599.00",
            "proposed_selling_price": "549.00",
            "estimated_shipping_cost": "60.00",
            "estimated_return_rate": 0.04,
            "target_customer": "Eco-conscious urban buyers",
            "key_features": ["100% natural bamboo", "Dishwasher safe"],
            "verdict": "RECOMMENDED",
            "reasoning": "High margin and strong consumer demand.",
        }

        res = submit_result(task_id, valid_output, prompt_tokens=150, completion_tokens=180)
        self.assertTrue(res["ok"])
        self.assertEqual(res["data"]["status"], "Succeeded")

        status_res = get_task_status(task_id)
        self.assertTrue(status_res["ok"])
        self.assertEqual(status_res["data"]["status"], "Succeeded")
        self.assertEqual(status_res["data"]["output_validated"], 1)

    def test_A5_financial_firewall_on_po_submit_api(self) -> None:
        """ACOM Manager gets 403 on PO or Refund approval; ACOM Finance succeeds."""
        frappe.set_user("api_editor@acom.local")
        app_res = create_approval(
            action_type="SubmitPurchaseOrder",
            related_doctype="Purchase Order",
            related_name="PO-TEST-FIREWALL",
            recommendation="Submit PO",
            estimated_financial_impact=-20000.0,
        )
        request_id = app_res["data"]["request_id"]

        # ACOM Manager tries to approve PO -> FORBIDDEN (403)
        frappe.set_user("api_manager@acom.local")
        dec_res = decide_approval(request_id, "Approved")
        self.assertFalse(dec_res["ok"])
        self.assertEqual(dec_res["error"]["code"], "FORBIDDEN")

        # ACOM Finance approves PO -> SUCCESS (200)
        frappe.set_user("api_finance@acom.local")
        ok_res = decide_approval(request_id, "Approved")
        self.assertTrue(ok_res["ok"])
        self.assertEqual(ok_res["data"]["approval_status"], "Approved")
