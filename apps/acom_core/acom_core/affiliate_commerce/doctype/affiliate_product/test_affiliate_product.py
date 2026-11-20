"""Tests for Affiliate Product DocType validation, publish gates, and permissions."""

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

# Avoid pulling ERPNext's BootStrapTestData (calendar FY) on an India FY site;
# tests manage their own isolated fixtures cleanly.
IGNORE_TEST_RECORD_DEPENDENCIES = [
    "Affiliate Network",
    "Affiliate Campaign",
    "Item Group",
    "Currency",
]


def _ensure_category() -> str:
    leaf = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
    if leaf:
        return leaf
    if not frappe.db.exists("Item Group", "All Item Groups"):
        frappe.get_doc(
            {"doctype": "Item Group", "item_group_name": "All Item Groups", "is_group": 1}
        ).insert(ignore_permissions=True)
    if not frappe.db.exists("Item Group", "Test Affiliate Category"):
        frappe.get_doc(
            {
                "doctype": "Item Group",
                "item_group_name": "Test Affiliate Category",
                "parent_item_group": "All Item Groups",
                "is_group": 0,
            }
        ).insert(ignore_permissions=True)
    return "Test Affiliate Category"


class TestAffiliateProduct(IntegrationTestCase):
    def setUp(self) -> None:
        frappe.set_user("Administrator")
        self.category = _ensure_category()
        self.active_network = self._make_network("TEST-PROD-NET-ACTIVE", "Active", "tag")
        self.paused_network = self._make_network("TEST-PROD-NET-PAUSED", "Paused", "tag")

    def tearDown(self) -> None:
        frappe.set_user("Administrator")
        for name in frappe.get_all(
            "Affiliate Product",
            filters={"slug": ["like", "test-aprod-%"]},
            pluck="name",
        ):
            frappe.delete_doc("Affiliate Product", name, force=True, ignore_permissions=True)
        for net in ("TEST-PROD-NET-ACTIVE", "TEST-PROD-NET-PAUSED"):
            if frappe.db.exists("Affiliate Network", net):
                frappe.delete_doc("Affiliate Network", net, force=True, ignore_permissions=True)

    def _make_network(self, name: str, status: str, tracking_param: str) -> str:
        if frappe.db.exists("Affiliate Network", name):
            frappe.delete_doc("Affiliate Network", name, force=True, ignore_permissions=True)
        doc = frappe.get_doc(
            {
                "doctype": "Affiliate Network",
                "network_name": name,
                "program_type": "Marketplace",
                "report_format": "CSV",
                "tracking_param": tracking_param,
                "status": status,
            }
        ).insert()
        return doc.name

    def _base_product_dict(self, **overrides) -> dict:
        data = {
            "doctype": "Affiliate Product",
            "product_name": "Test Stainless Bottle",
            "slug": "test-aprod-bottle-1",
            "product_sku": "B0TEST0001",
            "marketplace": "Amazon",
            "affiliate_network": self.active_network,
            "affiliate_url": "https://www.amazon.in/dp/B0TEST0001?tag=acom-21",
            "category": self.category,
            "commission_type": "Percentage",
            "commission_rate": 8.5,
            "currency": "INR",
            "display_price": 799,
            "status": "Draft",
            "disclosure_required": 1,
            "content_review_status": "Not Reviewed",
        }
        data.update(overrides)
        return data

    def test_valid_draft_and_never_creates_erpnext_item(self) -> None:
        items_before = frappe.db.count("Item")
        doc = frappe.get_doc(self._base_product_dict()).insert()
        self.assertTrue(doc.name.startswith("APROD-"))
        self.assertEqual(frappe.db.count("Item"), items_before)

    def test_rejects_unsafe_url_schemes_and_missing_tracking_param(self) -> None:
        for bad_url in (
            "javascript:alert(1)",
            "data:text/html,<h1>xss</h1>",
            "ftp://example.com/item?tag=acom-21",
            "https://www.amazon.in/dp/B0TEST0001",  # missing `tag`
        ):
            with self.assertRaises(frappe.ValidationError):
                frappe.get_doc(
                    self._base_product_dict(slug="test-aprod-bad-url", affiliate_url=bad_url)
                ).insert()

    def test_slug_is_immutable_after_insert(self) -> None:
        doc = frappe.get_doc(self._base_product_dict(slug="test-aprod-immutable")).insert()
        doc.slug = "test-aprod-changed"
        with self.assertRaises(frappe.ValidationError):
            doc.save()

    def test_publish_gates_enforced(self) -> None:
        # 1. Missing approval -> blocked
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                self._base_product_dict(
                    slug="test-aprod-no-approval",
                    status="Published",
                    last_verified_date=nowdate(),
                    content_review_status="Not Reviewed",
                )
            ).insert()

        # 2. Stale verification (> 30 days) -> blocked
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                self._base_product_dict(
                    slug="test-aprod-stale-verify",
                    status="Published",
                    last_verified_date=add_days(nowdate(), -31),
                    content_review_status="Approved",
                )
            ).insert()

        # 3. Inactive network -> blocked
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                self._base_product_dict(
                    slug="test-aprod-paused-net",
                    affiliate_network=self.paused_network,
                    status="Published",
                    last_verified_date=nowdate(),
                    content_review_status="Approved",
                )
            ).insert()

        # 4. All publish gates met -> succeeds
        published = frappe.get_doc(
            self._base_product_dict(
                slug="test-aprod-valid-pub",
                status="Published",
                last_verified_date=nowdate(),
                content_review_status="Approved",
                disclosure_required=1,
            )
        ).insert()
        self.assertEqual(published.status, "Published")

    def test_commission_bounds_and_flat_amount_validation(self) -> None:
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                self._base_product_dict(slug="test-aprod-bad-rate", commission_rate=105)
            ).insert()

        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                self._base_product_dict(
                    slug="test-aprod-flat-missing",
                    commission_type="Flat",
                    commission_rate=0,
                    commission_flat_amount=0,
                )
            ).insert()

    def test_guest_has_zero_doctype_permissions(self) -> None:
        frappe.set_user("Guest")
        self.assertFalse(frappe.has_permission("Affiliate Product", "read"))
        self.assertFalse(frappe.has_permission("Affiliate Product", "write"))
        self.assertFalse(frappe.has_permission("Affiliate Product", "create"))
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc(self._base_product_dict(slug="test-aprod-guest")).insert()
