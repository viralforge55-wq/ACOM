"""Integration tests for Automation API and Workflows (API_CONTRACTS §5, MASTER_BLUEPRINT §11)."""

from __future__ import annotations

import json
import time
import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime
from acom_core.integration_management.security import (
    compute_hmac_signature,
    get_automation_hmac_secret,
    verify_m2m_signature,
)
from acom_core.api.automation import (
    get_event_status,
    inject_event,
    trigger_workflow,
)


class TestAutomationAPI(IntegrationTestCase):
    def setUp(self) -> None:
        frappe.set_user("Administrator")
        self.secret = get_automation_hmac_secret()

    def test_hmac_valid_signature_passes(self) -> None:
        """Valid HMAC-SHA256 signature and fresh timestamp pass verification."""
        raw_body = b'{"event_type": "test.ping", "data": "hello"}'
        ts = int(time.time())
        sig = compute_hmac_signature(raw_body, self.secret, ts)

        valid, err = verify_m2m_signature(
            raw_body=raw_body,
            signature=sig,
            timestamp=str(ts),
            secret=self.secret,
        )
        self.assertTrue(valid)
        self.assertIsNone(err)

    def test_hmac_tampered_payload_rejected(self) -> None:
        """Tampered payload fails HMAC verification with INVALID_SIGNATURE."""
        raw_body = b'{"amount": 100}'
        ts = int(time.time())
        sig = compute_hmac_signature(raw_body, self.secret, ts)

        tampered_body = b'{"amount": 1000}'
        valid, err = verify_m2m_signature(
            raw_body=tampered_body,
            signature=sig,
            timestamp=str(ts),
            secret=self.secret,
        )
        self.assertFalse(valid)
        self.assertEqual(err, "INVALID_SIGNATURE")

    def test_hmac_wrong_secret_rejected(self) -> None:
        """Signature generated with wrong secret fails verification."""
        raw_body = b'{"msg": "secure"}'
        ts = int(time.time())
        sig = compute_hmac_signature(raw_body, "wrong-attacker-secret", ts)

        valid, err = verify_m2m_signature(
            raw_body=raw_body,
            signature=sig,
            timestamp=str(ts),
            secret=self.secret,
        )
        self.assertFalse(valid)
        self.assertEqual(err, "INVALID_SIGNATURE")

    def test_hmac_missing_headers_rejected(self) -> None:
        """Missing signature or timestamp is rejected."""
        valid, err = verify_m2m_signature(
            raw_body=b'{}',
            signature=None,
            timestamp=str(int(time.time())),
            secret=self.secret,
        )
        self.assertFalse(valid)
        self.assertEqual(err, "MISSING_SIGNATURE_HEADERS")

    def test_hmac_expired_timestamp_rejected(self) -> None:
        """Timestamp exceeding 300s skew is rejected with EXPIRED_TIMESTAMP."""
        raw_body = b'{}'
        stale_ts = int(time.time()) - 301
        sig = compute_hmac_signature(raw_body, self.secret, stale_ts)

        valid, err = verify_m2m_signature(
            raw_body=raw_body,
            signature=sig,
            timestamp=str(stale_ts),
            secret=self.secret,
        )
        self.assertFalse(valid)
        self.assertEqual(err, "EXPIRED_TIMESTAMP")

    def test_inject_event_idempotency_duplicate_returns_409(self) -> None:
        """inject_event with same idempotency_key returns HTTP 409 DUPLICATE_EVENT."""
        idem_key = f"api_test_idem_{frappe.generate_hash(length=8)}"
        payload = {
            "event_type": "order.test",
            "idempotency_key": idem_key,
            "payload": {"test": True},
        }

        # Mock request data in frappe.local
        frappe.local.form_dict = payload
        res1 = inject_event()
        self.assertTrue(res1.get("ok"))
        self.assertEqual(res1.get("data", {}).get("processing_status"), "Received")

        # Second call with same idempotency_key
        res2 = inject_event()
        self.assertFalse(res2.get("ok"))
        self.assertEqual(res2.get("error", {}).get("code"), "DUPLICATE_EVENT")

    def test_trigger_workflow_product_research_success_and_failure(self) -> None:
        """Flow 1: Product research success path generates approval request; unviable margin rejects."""
        # Success path
        frappe.local.form_dict = {
            "workflow": "product_research",
            "parameters": {
                "keyword": "Copper Water Bottle",
                "category": "Home & Kitchen",
                "supplier_cost": 200.0,
                "estimated_retail_price": 500.0,
                "min_target_margin_pct": 15.0,
            },
        }
        res_succ = trigger_workflow()
        self.assertTrue(res_succ.get("ok"))
        self.assertTrue(res_succ.get("data", {}).get("viable"))
        self.assertTrue(res_succ.get("data", {}).get("approval_request_id"))

        # Failure path: unviable retail price (supplier cost higher than retail price)
        frappe.local.form_dict = {
            "workflow": "product_research",
            "parameters": {
                "keyword": "Unviable Cheap Pen",
                "category": "Office",
                "supplier_cost": 50.0,
                "estimated_retail_price": 40.0,
                "min_target_margin_pct": 20.0,
            },
        }
        res_fail = trigger_workflow()
        self.assertTrue(res_fail.get("ok"))
        self.assertFalse(res_fail.get("data", {}).get("viable"))

    def test_trigger_workflow_content_generation_success_and_banned_superlatives(self) -> None:
        """Flow 2: Content generation generates draft copy; banned superlatives are rejected."""
        # Ensure a draft product exists
        prod_name = f"Test Draft Mug {frappe.generate_hash(length=4)}"
        if not frappe.db.exists("Affiliate Product", {"product_name": prod_name}):
            net = frappe.get_all("Affiliate Network", limit=1, pluck="name")
            net_name = net[0] if net else "test-net"
            item_grp = frappe.get_all("Item Group", limit=1, pluck="name")
            grp_name = item_grp[0] if item_grp else "Products"

            p = frappe.get_doc({
                "doctype": "Affiliate Product",
                "product_name": prod_name,
                "slug": f"test-draft-mug-{frappe.generate_hash(length=6).lower()}",
                "product_sku": f"MUG-{frappe.generate_hash(length=4)}",
                "marketplace": "Amazon",
                "affiliate_network": net_name,
                "affiliate_url": "https://amazon.in/dp/B000TEST?tag=acom-21",
                "category": grp_name,
                "commission_rate": 8.0,
                "commission_type": "Percentage",
                "status": "Draft",
            })
            p.insert(ignore_permissions=True)
            prod_doc_name = p.name
        else:
            prod_doc_name = frappe.db.get_value("Affiliate Product", {"product_name": prod_name}, "name")

        # Success path
        frappe.local.form_dict = {
            "workflow": "content_generation",
            "parameters": {
                "product_doctype": "Affiliate Product",
                "product_name": prod_doc_name,
            },
        }
        res_succ = trigger_workflow()
        self.assertTrue(res_succ.get("ok"))
        self.assertTrue(res_succ.get("data", {}).get("approval_request_id"))

        # Failure path: banned superlative
        frappe.local.form_dict = {
            "workflow": "content_generation",
            "parameters": {
                "product_doctype": "Affiliate Product",
                "product_name": prod_doc_name,
                "mock_copy": {
                    "title": "The world's best mug on the planet",
                    "short_description": "Guaranteed 100% miracle cure coffee container.",
                },
            },
        }
        res_fail = trigger_workflow()
        self.assertTrue(res_fail.get("ok"))
        self.assertFalse(res_fail.get("data", {}).get("ok"))
        self.assertIn("banned superlative", res_fail.get("data", {}).get("error"))

    def test_trigger_workflow_supplier_monitor_stockout_and_margin_alert(self) -> None:
        """Flow 3: Supplier stockout sets Out of Stock; margin compression creates AI Approval Request."""
        # Ensure a Dropshipping Product exists
        # Ensure a Supplier exists
        suppliers = frappe.get_all("Supplier", limit=1, pluck="name")
        supplier_name = suppliers[0] if suppliers else None
        if not supplier_name:
            s = frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": "Test Monitor Supplier",
                "supplier_group": "All Supplier Groups",
                "supplier_type": "Company",
            })
            s.insert(ignore_permissions=True)
            supplier_name = s.name

        # Ensure an Item exists
        items = frappe.get_all("Item", limit=1, pluck="name")
        item_name = items[0] if items else None
        if not item_name:
            it = frappe.get_doc({
                "doctype": "Item",
                "item_code": "TEST-MON-ITEM",
                "item_name": "Test Monitor Item",
                "item_group": "Products",
                "is_stock_item": 1,
            })
            it.insert(ignore_permissions=True)
            item_name = it.name

        sku = f"SUP-TEST-{frappe.generate_hash(length=4)}"
        p = frappe.get_doc({
            "doctype": "Dropshipping Product",
            "product_name": f"Test Monitor Product {sku}",
            "slug": f"test-mon-{sku.lower()}",
            "supplier_sku": sku,
            "supplier": supplier_name,
            "erpnext_item": item_name,
            "supplier_cost": 100.0,
            "selling_price": 250.0,
            "shipping_cost": 50.0,
            "hsn_code": "123456",
            "gst_rate": 18.0,
            "supplier_stock": 25,
            "status": "Draft",
        })
        p.insert(ignore_permissions=True)

        # Trigger monitor with stock=0 and cost increase to 240 (margin collapses)
        frappe.local.form_dict = {
            "workflow": "supplier_monitor",
            "parameters": {
                "feed_items": [
                    {"supplier_sku": sku, "stock": 0, "cost": 240.0}
                ]
            },
        }
        res = trigger_workflow()
        self.assertTrue(res.get("ok"))
        self.assertEqual(res.get("data", {}).get("updated_count"), 1)
        self.assertGreaterEqual(res.get("data", {}).get("alerts_count"), 1)

        # Confirm product stock changed to 0 and Out of Stock, but selling_price remains unchanged!
        reloaded = frappe.get_doc("Dropshipping Product", p.name)
        self.assertEqual(reloaded.supplier_stock, 0)
        self.assertEqual(reloaded.status, "Out of Stock")
        self.assertEqual(reloaded.selling_price, 250.0)

    def test_trigger_workflow_order_monitor_and_a5_firewall(self) -> None:
        """Flow 4: Order monitor runs cleanly and respects A5 Financial Firewall (zero auto-POs)."""
        frappe.local.form_dict = {
            "workflow": "order_monitor",
            "parameters": {
                "stuck_checkout_minutes": 1,
                "stale_po_hours": 1,
            },
        }
        res = trigger_workflow()
        self.assertTrue(res.get("ok"))
        self.assertIn("event_id", res.get("data", {}))
        self.assertIn("stuck_checkouts_count", res.get("data", {}))

    def test_trigger_workflow_reconciliation_monitor(self) -> None:
        """Flow 5: Reconciliation monitor checks orphan conversions and overdue payouts."""
        frappe.local.form_dict = {
            "workflow": "reconciliation_monitor",
            "parameters": {
                "overdue_pending_days": 1,
            },
        }
        res = trigger_workflow()
        self.assertTrue(res.get("ok"))
        self.assertIn("event_id", res.get("data", {}))
        self.assertIn("orphan_count", res.get("data", {}))
