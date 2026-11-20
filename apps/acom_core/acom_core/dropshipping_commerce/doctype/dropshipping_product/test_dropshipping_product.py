"""Phase 5 transaction/security gates. Each test rolls back only its own savepoint."""
import json
import time
import uuid
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from acom_core.api.errors import AcomApiError
from acom_core.dropshipping_commerce.services.cart_service import validate_and_price_cart
from acom_core.dropshipping_commerce.services.checkout_service import create_dropship_checkout, get_scoped_customer_order
from acom_core.dropshipping_commerce.services.payment_gateway import compute_webhook_signature
from acom_core.dropshipping_commerce.services.webhook_service import handle_payment_webhook
from acom_core.dropshipping_commerce.services.fulfillment_service import process_payment_confirmed_event, approve_and_submit_purchase_order

IGNORE_TEST_RECORD_DEPENDENCIES = ["Item", "Supplier", "Price List", "Item Group", "Currency"]


class TestDropshippingTransactionEngine(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        frappe.db.savepoint("phase5_test")
        self.addCleanup(self.cleanup_test)
        self.secret_patch = patch.dict(frappe.conf, {
            "acom_payment_webhook_secret": uuid.uuid4().hex + uuid.uuid4().hex,
            "acom_cart_signing_secret": uuid.uuid4().hex + uuid.uuid4().hex,
        })
        self.secret_patch.start()
        self.addCleanup(self.secret_patch.stop)
        self.slug = "test-p5-" + uuid.uuid4().hex[:10]
        group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
        supplier = frappe.get_doc({"doctype": "Supplier", "supplier_name": self.slug,
            "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
            "country": "India"}).insert()
        item = frappe.get_doc({"doctype": "Item", "item_code": self.slug, "item_name": self.slug,
            "item_group": group, "stock_uom": "Nos", "is_stock_item": 0,
            "gst_hsn_code": "847130"}).insert()
        frappe.get_doc({"doctype": "Item Price", "item_code": item.name,
            "price_list": "Standard Selling", "selling": 1, "currency": "INR", "price_list_rate": 549}).insert()
        self.product = frappe.get_doc({"doctype": "Dropshipping Product", "product_name": self.slug,
            "slug": self.slug, "erpnext_item": item.name, "supplier": supplier.name,
            "supplier_sku": self.slug, "selling_price": 549, "supplier_cost": 220,
            "shipping_cost": 60, "hsn_code": "847130", "gst_rate": 18,
            "supplier_stock": 25, "status": "Published", "content_review_status": "Approved"}).insert()
        self.users = []
        for suffix in ("a", "b"):
            user = frappe.get_doc({"doctype": "User", "email": f"{self.slug}-{suffix}@example.invalid",
                "first_name": "Synthetic", "send_welcome_email": 0,
                "roles": [{"role": "Customer"}]}).insert()
            self.users.append(user.name)

    def cleanup_test(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="phase5_test")

    def checkout(self, **extra):
        cart = validate_and_price_cart([{"product_slug": self.slug, "quantity": 1}])["public"]
        frappe.set_user(self.users[0])
        body = {"cart_token": cart["cart_token"], "customer": {
            "name": "Synthetic Customer", "email": self.users[0], "phone": "+919876543210"},
            "shipping_address": {"line1": "Test Road", "city": "Bengaluru", "state": "Karnataka",
                "pincode": "560001", "country": "IN"}, **extra}
        key = str(uuid.uuid4())
        response, status = create_dropship_checkout(idempotency_key=key, body=body)
        return response, key, body

    def webhook(self, checkout, *, event=None, amount="549.00", signature=None, age=0):
        timestamp = str(int(time.time()) - age)
        raw = json.dumps({"order_ref": checkout["payment"]["order_ref"],
            "payment_id": "pay-" + checkout["checkout_id"], "amount": amount,
            "currency": "INR", "status": "captured"}).encode()
        with patch("frappe.enqueue"):
            return handle_payment_webhook(raw_body=raw,
                signature=signature if signature is not None else compute_webhook_signature(timestamp, raw),
                timestamp=timestamp, event_id=event or uuid.uuid4().hex)

    def consume(self, checkout):
        event = frappe.db.get_value("Automation Event", {"aggregate_name": checkout["checkout_id"],
            "event_type": "payment.confirmed"}, "name")
        result = process_payment_confirmed_event(event)
        if result["status"] == "Failed":
            result["diagnostic"] = frappe.db.get_value("Error Log", {"method": "ACOM ERP sync failed for " + checkout["checkout_id"]}, "error", order_by="creation desc")
        return result

    def test_checkout_idempotency_and_owner_scope(self):
        checkout, key, body = self.checkout()
        replay, status = create_dropship_checkout(idempotency_key=key, body=body)
        self.assertEqual(status, 200)
        self.assertEqual(replay["checkout_id"], checkout["checkout_id"])
        self.assertFalse(frappe.db.get_value("Dropship Checkout", checkout["checkout_id"], "sales_order"))
        with self.assertRaises(AcomApiError):
            create_dropship_checkout(idempotency_key=key, body={**body, "expected_total": "1"})
        self.assertEqual(get_scoped_customer_order(checkout["checkout_id"])["checkout_id"], checkout["checkout_id"])
        frappe.set_user(self.users[1])
        with self.assertRaises(AcomApiError) as error:
            get_scoped_customer_order(checkout["checkout_id"])
        self.assertEqual(error.exception.status_code, 403)

    def test_price_discount_currency_tampering(self):
        for extra in ({"expected_total": "1"}, {"discount": "500"}, {"currency": "USD"}, {"price": "1"}):
            with self.subTest(extra=extra), self.assertRaises(AcomApiError):
                self.checkout(**extra)
        with self.assertRaises(AcomApiError):
            validate_and_price_cart([{"product_slug": self.slug, "quantity": 1, "price": "1"}])

    def test_webhook_auth_amount_and_replay(self):
        checkout, _, _ = self.checkout()
        for kwargs in ({"signature": "invalid"}, {"signature": ""}, {"age": 301}, {"amount": "1.00"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(AcomApiError):
                self.webhook(checkout, **kwargs)
        self.assertEqual(frappe.db.get_value("Dropship Checkout", checkout["checkout_id"], "status"), "PendingPayment")
        result, status = self.webhook(checkout, event="event-" + self.slug)
        self.assertEqual(status, 200)
        self.assertFalse(result["duplicate"])
        self.assertTrue(self.webhook(checkout, event="event-" + self.slug)[0]["duplicate"])
        self.assertTrue(self.webhook(checkout)[0]["duplicate"])

    def test_paid_order_creates_so_and_draft_po(self):
        checkout, _, _ = self.checkout()
        self.webhook(checkout)
        result = self.consume(checkout)
        self.assertEqual(result["status"], "Completed", result)
        self.assertEqual(frappe.db.get_value("Sales Order", result["sales_order"], "docstatus"), 1)
        po = result["purchase_orders"][0]
        self.assertEqual(frappe.db.get_value("Purchase Order", po, "docstatus"), 0)
        self.assertEqual(self.consume(checkout)["status"], "Completed")
        with self.assertRaises(AcomApiError):
            approve_and_submit_purchase_order(checkout_id=checkout["checkout_id"])
        frappe.set_user("Administrator")
        approve_and_submit_purchase_order(checkout_id=checkout["checkout_id"], note="Synthetic approval")
        self.assertEqual(frappe.db.get_value("Purchase Order", po, "docstatus"), 1)

    def test_erp_failure_rollback_and_retry(self):
        checkout, _, _ = self.checkout()
        self.webhook(checkout)
        before = frappe.db.count("Sales Order")
        with patch("acom_core.dropshipping_commerce.services.fulfillment_service._default_company_and_warehouse", side_effect=RuntimeError("synthetic failure")):
            self.assertEqual(self.consume(checkout)["status"], "Failed")
        self.assertEqual(frappe.db.count("Sales Order"), before)
        self.assertEqual(frappe.db.get_value("Dropship Checkout", checkout["checkout_id"], "status"), "Paid")
        self.assertEqual(self.consume(checkout)["status"], "Completed")
