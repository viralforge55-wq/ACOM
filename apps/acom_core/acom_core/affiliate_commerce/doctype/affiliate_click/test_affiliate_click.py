"""Tests for Affiliate Click DocType invariants and permissions."""

from __future__ import annotations

import uuid

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from acom_core.affiliate_commerce.doctype.affiliate_product.test_affiliate_product import (
    _ensure_category,
)

IGNORE_TEST_RECORD_DEPENDENCIES = ["Affiliate Product", "Item Group", "Currency"]


class TestAffiliateClick(IntegrationTestCase):
    def setUp(self) -> None:
        frappe.set_user("Administrator")
        category = _ensure_category()
        self.network = frappe.get_doc(
            {
                "doctype": "Affiliate Network",
                "network_name": "TEST-CLK-NET",
                "program_type": "Marketplace",
                "report_format": "CSV",
                "tracking_param": "tag",
                "status": "Active",
            }
        ).insert()
        self.campaign = frappe.get_doc(
            {
                "doctype": "Affiliate Campaign",
                "campaign_name": "TEST-CLK-CAMP",
                "affiliate_network": self.network.name,
                "status": "Active",
            }
        ).insert()
        self.product = frappe.get_doc(
            {
                "doctype": "Affiliate Product",
                "product_name": "Test Click Product",
                "slug": "test-clk-prod",
                "product_sku": "B0CLK0001",
                "marketplace": "Amazon",
                "affiliate_network": self.network.name,
                "affiliate_url": "https://www.amazon.in/dp/B0CLK0001?tag=acom-21",
                "category": category,
                "campaign": self.campaign.name,
                "commission_type": "Percentage",
                "commission_rate": 5,
                "currency": "INR",
                "status": "Published",
                "last_verified_date": nowdate(),
                "content_review_status": "Approved",
                "disclosure_required": 1,
            }
        ).insert()

    def tearDown(self) -> None:
        frappe.set_user("Administrator")
        for name in frappe.get_all(
            "Affiliate Click",
            filters={"affiliate_product": self.product.name},
            pluck="name",
        ):
            frappe.delete_doc("Affiliate Click", name, force=True, ignore_permissions=True)
        if frappe.db.exists("Affiliate Product", self.product.name):
            frappe.delete_doc("Affiliate Product", self.product.name, force=True, ignore_permissions=True)
        if frappe.db.exists("Affiliate Campaign", self.campaign.name):
            frappe.delete_doc("Affiliate Campaign", self.campaign.name, force=True, ignore_permissions=True)
        if frappe.db.exists("Affiliate Network", self.network.name):
            frappe.delete_doc("Affiliate Network", self.network.name, force=True, ignore_permissions=True)

    def test_server_generated_uuid_timestamp_and_campaign_copy(self) -> None:
        client_fake_ts = add_days(nowdate(), -90)
        doc = frappe.get_doc(
            {
                "doctype": "Affiliate Click",
                "click_id": "client-forged-id",
                "affiliate_product": self.product.name,
                "session_id": "s_anon_session_12345",
                "source": "google",
                "medium": "organic",
                "landing_path": "/products/test-clk-prod",
                "clicked_at": client_fake_ts,
                "user_agent_family": "Chrome",
            }
        ).insert()

        self.assertNotEqual(doc.click_id, "client-forged-id")
        parsed = uuid.UUID(doc.click_id, version=4)
        self.assertEqual(str(parsed), doc.click_id)
        self.assertEqual(doc.name, doc.click_id)
        self.assertEqual(doc.campaign_id, self.campaign.name)
        self.assertEqual(doc.attribution_status, "Recorded")
        self.assertNotEqual(str(doc.clicked_at)[:10], str(client_fake_ts))

    def test_long_referrer_truncated_to_host_only(self) -> None:
        long_ref = "https://search.example.com/" + ("a" * 600)
        doc = frappe.get_doc(
            {
                "doctype": "Affiliate Click",
                "affiliate_product": self.product.name,
                "session_id": "s_anon_session_ref",
                "referrer": long_ref,
                "user_agent_family": "Safari",
            }
        ).insert()
        self.assertEqual(doc.referrer, "search.example.com")

    def test_immutability_and_allowed_attribution_update(self) -> None:
        doc = frappe.get_doc(
            {
                "doctype": "Affiliate Click",
                "affiliate_product": self.product.name,
                "session_id": "s_anon_immutable_1",
                "source": "google",
                "user_agent_family": "Chrome",
            }
        ).insert()

        # Allowed: updating attribution_status
        doc.attribution_status = "Matched"
        doc.save()
        self.assertEqual(doc.attribution_status, "Matched")

        # Forbidden: mutating session_id or source
        doc.session_id = "s_tampered_session"
        with self.assertRaises(frappe.ValidationError):
            doc.save()

    def test_rejects_raw_ua_and_invalid_source(self) -> None:
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                {
                    "doctype": "Affiliate Click",
                    "affiliate_product": self.product.name,
                    "session_id": "s_bad_ua_session",
                    "user_agent_family": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
                }
            ).insert()

        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                {
                    "doctype": "Affiliate Click",
                    "affiliate_product": self.product.name,
                    "session_id": "s_bad_src_session",
                    "source": "unlisted-spam-source",
                }
            ).insert()

    def test_guest_has_no_direct_doctype_access(self) -> None:
        frappe.set_user("Guest")
        self.assertFalse(frappe.has_permission("Affiliate Click", "read"))
        self.assertFalse(frappe.has_permission("Affiliate Click", "create"))
        self.assertFalse(frappe.has_permission("Affiliate Click", "delete"))
