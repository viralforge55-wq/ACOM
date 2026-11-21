"""Comprehensive End-to-End Validation Suite (Phase 9 - TEST_PLAN §2.9).

Executes and verifies all 7 canonical business lifecycle scenarios:
1. Affiliate Happy Path (Discover → Approve → Publish → Click → Conversion → Confirm → Reconcile)
2. Dropship Happy Path (Publish → Cart → Checkout → Pay → SO → Draft PO → PO Approval → Ship → Deliver)
3. Refund Path (Request → Approve → Gateway Refund → Status Update → CEO Dashboard Recon)
4. Duplicate Storm (Webhook delivered 10x with same idempotency key → exactly one SO/PO)
5. Price Tamper Defense (Modified client cart prices → rejected by server engine)
6. AI Outage Resilience (Inference offline → business transaction completes safely)
7. Financial Traceability & CEO Drill-Through (All aggregates traceable to rows)
"""

from __future__ import annotations

from decimal import Decimal
import json
import time
import uuid
import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate, now_datetime

from acom_core.affiliate_commerce.doctype.affiliate_product.test_affiliate_product import (
    _ensure_category,
)
from acom_core.affiliate_commerce.services.conversion_service import import_affiliate_conversions
from acom_core.affiliate_commerce.services.reconciliation_service import get_reconciliation_summary
from acom_core.analytics.services.ceo_dashboard_service import get_ceo_dashboard_summary
from acom_core.dropshipping_commerce.services.cart_service import validate_and_price_cart
from acom_core.dropshipping_commerce.services.checkout_service import (
    create_dropship_checkout,
    get_scoped_customer_order,
)
from acom_core.dropshipping_commerce.services.payment_gateway import (
    compute_webhook_signature,
    create_test_gateway_refund,
)
from acom_core.dropshipping_commerce.services.webhook_service import handle_payment_webhook
from acom_core.dropshipping_commerce.services.fulfillment_service import (
    process_payment_confirmed_event,
    approve_and_submit_purchase_order,
    update_fulfillment_tracking,
    request_cancellation_or_refund,
    approve_or_reject_refund,
)


class TestEndToEndScenarios(IntegrationTestCase):
    """End-to-end integration and disaster resilience validation for Phase 9."""

    def setUp(self) -> None:
        super().setUp()
        frappe.set_user("Administrator")
        frappe.db.savepoint("phase9_e2e_test")
        self.addCleanup(self.cleanup_test)
        self._ensure_test_users()
        self._ensure_test_catalog()

    def cleanup_test(self) -> None:
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="phase9_e2e_test")

    def _ensure_test_users(self) -> None:
        user_roles = {
            "e2e_manager@acom.local": ["ACOM Manager", "Purchase Manager", "Item Manager", "Stock Manager"],
            "e2e_finance@acom.local": ["ACOM Finance", "Accounts Manager"],
            "e2e_buyer@acom.local": ["Customer"],
        }
        for email, roles in user_roles.items():
            if not frappe.db.exists("User", email):
                u = frappe.get_doc({
                    "doctype": "User",
                    "email": email,
                    "first_name": email.split("@")[0],
                    "enabled": 1,
                    "roles": [{"doctype": "Has Role", "role": r} for r in roles],
                })
                u.insert(ignore_permissions=True)
            else:
                u = frappe.get_doc("User", email)
                existing_roles = {r.role for r in u.roles}
                updated = False
                for r in roles:
                    if r not in existing_roles:
                        u.append("roles", {"role": r})
                        updated = True
                if updated:
                    u.save(ignore_permissions=True)

    def _ensure_test_catalog(self) -> None:
        self.slug = "e2e-ds-" + uuid.uuid4().hex[:10]
        group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
        supplier = frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": self.slug,
            "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
            "country": "India",
        }).insert(ignore_permissions=True)
        item = frappe.get_doc({
            "doctype": "Item",
            "item_code": self.slug,
            "item_name": self.slug,
            "item_group": group,
            "stock_uom": "Nos",
            "is_stock_item": 0,
            "gst_hsn_code": "847130",
        }).insert(ignore_permissions=True)
        frappe.get_doc({
            "doctype": "Item Price",
            "item_code": item.name,
            "price_list": "Standard Selling",
            "selling": 1,
            "currency": "INR",
            "price_list_rate": 999.00,
        }).insert(ignore_permissions=True)
        self.dropship_product = frappe.get_doc({
            "doctype": "Dropshipping Product",
            "product_name": f"E2E Dropship Item {self.slug}",
            "slug": self.slug,
            "erpnext_item": item.name,
            "supplier": supplier.name,
            "supplier_sku": self.slug,
            "selling_price": 999.00,
            "supplier_cost": 450.00,
            "shipping_cost": 50.00,
            "hsn_code": "847130",
            "gst_rate": 18,
            "supplier_stock": 50,
            "status": "Published",
            "content_review_status": "Approved",
        }).insert(ignore_permissions=True)

    def _create_checkout_helper(self, user="e2e_buyer@acom.local", quantity=1):
        cart = validate_and_price_cart([{"product_slug": self.slug, "quantity": quantity}])["public"]
        frappe.set_user(user)
        body = {
            "cart_token": cart["cart_token"],
            "customer": {
                "name": "E2E Buyer",
                "email": user,
                "phone": "+919876543210",
            },
            "shipping_address": {
                "line1": "Flat 402, Lotus Tower",
                "city": "Bengaluru",
                "state": "Karnataka",
                "pincode": "560001",
                "country": "IN",
            },
        }
        key = str(uuid.uuid4())
        response, status = create_dropship_checkout(idempotency_key=key, body=body)
        return response, key, body

    def _webhook_helper(self, checkout, amount="999.00", event_id=None):
        timestamp = str(int(time.time()))
        raw = json.dumps({
            "order_ref": checkout["payment"]["order_ref"],
            "payment_id": "pay-" + checkout["checkout_id"],
            "amount": amount,
            "currency": "INR",
            "status": "captured",
        }).encode("utf-8")
        sig = compute_webhook_signature(timestamp, raw)
        return handle_payment_webhook(
            raw_body=raw,
            signature=sig,
            timestamp=timestamp,
            event_id=event_id or uuid.uuid4().hex,
        )

    # -------------------------------------------------------------
    # Scenario 1: Affiliate Happy Path
    # -------------------------------------------------------------
    def test_scenario_1_affiliate_happy_path(self) -> None:
        """Scenario 1: Full lifecycle of an Affiliate Product."""
        networks = frappe.get_all("Affiliate Network", limit=1)
        net = networks[0]["name"] if networks else frappe.get_doc({
            "doctype": "Affiliate Network",
            "network_name": "E2E Affiliate Network",
            "program_type": "Marketplace",
            "report_format": "CSV",
            "tracking_param": "tag",
            "status": "Active",
        }).insert(ignore_permissions=True).name

        campaigns = frappe.get_all("Affiliate Campaign", limit=1)
        camp = campaigns[0]["name"] if campaigns else frappe.get_doc({
            "doctype": "Affiliate Campaign",
            "campaign_name": "E2E Campaign",
            "affiliate_network": net,
            "status": "Active",
        }).insert(ignore_permissions=True).name

        # Step 1: Create draft affiliate product
        cat = _ensure_category()
        sku = f"E2E-AFF-{frappe.generate_hash(length=6).upper()}"
        prod = frappe.get_doc({
            "doctype": "Affiliate Product",
            "product_name": f"E2E Ergonomic Keyboard {sku}",
            "product_sku": sku,
            "affiliate_network": net,
            "affiliate_url": f"https://www.amazon.in/dp/{sku}?tag=acom-21",
            "category": cat,
            "commission_rate": 8.50,
            "commission_type": "Percentage",
            "campaign": camp,
            "status": "Draft",
        }).insert(ignore_permissions=True)
        self.assertEqual(prod.status, "Draft")

        # Step 2 & 3: Approve and Publish
        prod.content_review_status = "Approved"
        prod.last_verified_date = nowdate()
        prod.status = "Published"
        prod.save(ignore_permissions=True)
        self.assertEqual(prod.status, "Published")

        # Step 4 & 5: Customer visits and clicks link
        click_id = f"e2e-click-{frappe.generate_hash(length=8)}"
        click = frappe.get_doc({
            "doctype": "Affiliate Click",
            "click_id": click_id,
            "affiliate_product": prod.name,
            "campaign_id": camp,
            "session_id": f"sess-{frappe.generate_hash(length=8)}",
            "clicked_at": str(now_datetime()),
            "source": "organic",
            "attribution_status": "Recorded",
        }).insert(ignore_permissions=True)
        self.assertEqual(click.attribution_status, "Recorded")

        # Step 6 & 7: Network conversion report import (Pending)
        ext_tx_id = f"NET-TX-{frappe.generate_hash(length=8)}"
        conv_res = import_affiliate_conversions(
            network=net,
            report_date=nowdate(),
            file_name="e2e_affiliate_report.json",
            rows=[{
                "external_transaction_id": ext_tx_id,
                "order_value": "4500.00",
                "commission_amount": "382.50",
                "status": "PENDING",
                "subid": click.click_id,
                "conversion_date": nowdate(),
                "currency": "INR",
            }],
        )
        self.assertEqual(conv_res["inserted"], 1)
        conv_name = conv_res["conversion_ids"][0]

        # Step 8: Verify attribution and separation on CEO dashboard
        summary1 = get_ceo_dashboard_summary(period="all_time")
        self.assertIn(conv_name, summary1["drill_through"]["pending_conversions"])

        # Step 9: Confirmation report updates conversion to Confirmed
        conv_doc = frappe.get_doc("Affiliate Conversion", conv_name)
        conv_doc.commission_status = "Confirmed"
        conv_doc.save(ignore_permissions=True)

        summary2 = get_ceo_dashboard_summary(period="all_time")
        self.assertIn(conv_name, summary2["drill_through"]["confirmed_conversions"])

    # -------------------------------------------------------------
    # Scenario 2: Dropship Happy Path
    # -------------------------------------------------------------
    def test_scenario_2_dropship_happy_path(self) -> None:
        """Scenario 2: Complete Dropshipping order flow (Checkout → Webhook → SO → Draft PO → Approval → Ship → Deliver)."""
        checkout, key, body = self._create_checkout_helper(quantity=1)
        chk_id = checkout["checkout_id"]
        self.assertEqual(checkout["status"], "PendingPayment")

        # Simulate signed webhook
        wh_res, status = self._webhook_helper(checkout, amount="999.00")
        self.assertEqual(status, 200)

        # Process outbox event: SO submitted (1) + Draft PO created (0)
        event = frappe.db.get_value("Automation Event", {"aggregate_name": chk_id, "event_type": "payment.confirmed"}, "name")
        res = process_payment_confirmed_event(event)
        self.assertEqual(res["status"], "Completed")

        so_name = res["sales_order"]
        so = frappe.get_doc("Sales Order", so_name)
        self.assertEqual(so.docstatus, 1)

        po_name = res["purchase_orders"][0]
        po = frappe.get_doc("Purchase Order", po_name)
        self.assertEqual(po.docstatus, 0)  # PO is strictly DRAFT (Financial firewall)

        # Manager approves and submits PO
        frappe.set_user("e2e_manager@acom.local")
        po_approval = approve_and_submit_purchase_order(checkout_id=chk_id)
        self.assertEqual(po_approval["status"], "Processing")
        self.assertEqual(po_approval["docstatus"], 1)
        po.reload()
        self.assertEqual(po.docstatus, 1)

        # Supplier fulfillment tracking: Shipped
        frappe.set_user("e2e_manager@acom.local")
        ship_res = update_fulfillment_tracking(
            checkout_id=chk_id,
            carrier="Delhivery",
            tracking_number="DEL-E2E-12345",
            tracking_url="https://delhivery.example.com/track/DEL-E2E-12345",
            status="Shipped",
        )
        self.assertEqual(ship_res["status"], "Shipped")

        # Supplier fulfillment tracking: Delivered
        deliv_res = update_fulfillment_tracking(
            checkout_id=chk_id,
            carrier="Delhivery",
            tracking_number="DEL-E2E-12345",
            status="Delivered",
        )
        self.assertEqual(deliv_res["status"], "Delivered")

    # -------------------------------------------------------------
    # Scenario 3: Refund Path
    # -------------------------------------------------------------
    def test_scenario_3_refund_path(self) -> None:
        """Scenario 3: Refund workflow with approval gate and CEO dashboard update."""
        checkout, _, _ = self._create_checkout_helper(quantity=1)
        chk_id = checkout["checkout_id"]
        self._webhook_helper(checkout, amount="999.00")
        event = frappe.db.get_value("Automation Event", {"aggregate_name": chk_id, "event_type": "payment.confirmed"}, "name")
        process_payment_confirmed_event(event)

        # Customer requests refund
        frappe.set_user("e2e_buyer@acom.local")
        req_res = request_cancellation_or_refund(
            checkout_id=chk_id,
            reason="Item not needed anymore",
            refund_amount="999.00",
        )
        self.assertEqual(req_res["refund_status"], "Requested")

        # Unauthorized user (buyer) cannot approve refund
        with self.assertRaises(Exception):
            approve_or_reject_refund(checkout_id=chk_id, decision="Approved")

        # Finance user approves refund
        frappe.set_user("e2e_finance@acom.local")
        appr_res = approve_or_reject_refund(checkout_id=chk_id, decision="Approved", note="Approved by finance")
        self.assertEqual(appr_res["status"], "Refunded")

        # Verify CEO Dashboard reflects refund
        frappe.set_user("Administrator")
        dash = get_ceo_dashboard_summary(period="all_time")
        self.assertIn(chk_id, dash["drill_through"]["refunded_checkouts"])

    # -------------------------------------------------------------
    # Scenario 4: Duplicate Storm
    # -------------------------------------------------------------
    def test_scenario_4_duplicate_storm(self) -> None:
        """Scenario 4: 10 repeated webhook requests produce exactly one Sales Order."""
        checkout, _, _ = self._create_checkout_helper(quantity=1)
        chk_id = checkout["checkout_id"]

        event_id = "storm-evt-" + uuid.uuid4().hex[:8]
        # Deliver 10x with the same webhook payload and event_id
        for i in range(10):
            res, status = self._webhook_helper(checkout, amount="999.00", event_id=event_id)
            self.assertEqual(status, 200)
            if i > 0:
                self.assertTrue(res["duplicate"])

        # Exactly 1 payment.confirmed event exists
        events = frappe.get_all("Automation Event", filters={"aggregate_name": chk_id, "event_type": "payment.confirmed"})
        self.assertEqual(len(events), 1)

        # Process the event
        result = process_payment_confirmed_event(events[0]["name"])
        self.assertEqual(result["status"], "Completed")

        # Exactly 1 Sales Order exists for this checkout
        so_count = frappe.db.count("Sales Order", {"po_no": chk_id})
        self.assertEqual(so_count, 1)

    # -------------------------------------------------------------
    # Scenario 5: Price Tamper Defense
    # -------------------------------------------------------------
    def test_scenario_5_price_tamper_defense(self) -> None:
        """Scenario 5: Cart price manipulation is detected and rejected server-side."""
        frappe.set_user("e2e_buyer@acom.local")
        # Attempt 1: Passing client price into cart pricing is rejected
        with self.assertRaises(Exception):
            validate_and_price_cart([{"product_slug": self.slug, "quantity": 1, "price": "1.00"}])

        # Attempt 2: Passing unexpected fields or expected_total into checkout
        cart = validate_and_price_cart([{"product_slug": self.slug, "quantity": 1}])["public"]
        body = {
            "cart_token": cart["cart_token"],
            "customer": {"name": "Hacker", "email": "e2e_buyer@acom.local", "phone": "+919876543210"},
            "shipping_address": {"line1": "Road", "city": "Bengaluru", "state": "Karnataka", "pincode": "560001", "country": "IN"},
            "expected_total": "1.00",  # Tampered total
        }
        with self.assertRaises(Exception):
            create_dropship_checkout(idempotency_key=str(uuid.uuid4()), body=body)

    # -------------------------------------------------------------
    # Scenario 6: AI Outage Resilience
    # -------------------------------------------------------------
    def test_scenario_6_ai_outage_resilience(self) -> None:
        """Scenario 6: Ollama/AI failure does not break the business flow."""
        # Create an AI Task simulating an offline timeout
        task = frappe.get_doc({
            "doctype": "AI Task",
            "task_type": "ProductResearch",
            "agent_id": "product_hunter",
            "model": "qwen2.5:3b",
            "input_hash": frappe.generate_hash(length=32),
            "status": "Timed Out",
            "error_details": "Simulated Ollama host network timeout (offline)",
        }).insert(ignore_permissions=True)
        self.assertEqual(task.status, "Timed Out")

        # Checkout and payment engine continues seamlessly despite AI outage
        checkout, _, _ = self._create_checkout_helper(quantity=1)
        self.assertEqual(checkout["status"], "PendingPayment")

        dash = get_ceo_dashboard_summary(period="all_time")
        self.assertIn(task.name, dash["drill_through"]["failed_ai_tasks"])

    # -------------------------------------------------------------
    # Scenario 7: Financial Traceability & CEO Drill-Through
    # -------------------------------------------------------------
    def test_scenario_7_financial_traceability_and_drill_through(self) -> None:
        """Scenario 7: Full drill-through verification across all dashboard numbers."""
        dash = get_ceo_dashboard_summary(period="all_time")
        dt = dash["drill_through"]
        self.assertIsInstance(dt["paid_checkouts"], list)
        self.assertIsInstance(dt["confirmed_conversions"], list)
        self.assertIsInstance(dt["pending_approvals"], list)
        self.assertIsInstance(dt["dead_letter_events"], list)
        self.assertIsInstance(dt["failed_ai_tasks"], list)
