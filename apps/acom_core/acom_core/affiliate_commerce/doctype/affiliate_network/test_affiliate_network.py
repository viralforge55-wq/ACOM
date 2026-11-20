"""Tests for Affiliate Network DocType."""

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase


class TestAffiliateNetwork(IntegrationTestCase):
    def tearDown(self) -> None:
        frappe.set_user("Administrator")
        for name in frappe.get_all(
            "Affiliate Network",
            filters={"name": ["like", "TEST-NET-%"]},
            pluck="name",
        ):
            frappe.delete_doc("Affiliate Network", name, force=True, ignore_permissions=True)

    def test_create_and_slug_immutable(self) -> None:
        doc = frappe.get_doc(
            {
                "doctype": "Affiliate Network",
                "network_name": "TEST-NET-Amazon India",
                "program_type": "Marketplace",
                "report_format": "CSV",
                "tracking_param": "tag",
                "cookie_window_days": 1,
                "status": "Active",
            }
        ).insert()

        self.assertEqual(doc.slug, "test-net-amazon-india")

        doc.slug = "changed-slug"
        with self.assertRaises(frappe.ValidationError):
            doc.save()

    def test_invalid_tracking_param_and_negative_cookie_window_rejected(self) -> None:
        bad_param = frappe.get_doc(
            {
                "doctype": "Affiliate Network",
                "network_name": "TEST-NET-BadParam",
                "program_type": "Network",
                "report_format": "CSV",
                "tracking_param": "bad param!",
                "status": "Active",
            }
        )
        with self.assertRaises(frappe.ValidationError):
            bad_param.insert()

        bad_window = frappe.get_doc(
            {
                "doctype": "Affiliate Network",
                "network_name": "TEST-NET-BadWindow",
                "program_type": "Network",
                "report_format": "CSV",
                "cookie_window_days": -5,
                "status": "Active",
            }
        )
        with self.assertRaises(frappe.ValidationError):
            bad_window.insert()

    def test_guest_permission_denied(self) -> None:
        frappe.set_user("Guest")
        self.assertFalse(frappe.has_permission("Affiliate Network", "read"))
        self.assertFalse(frappe.has_permission("Affiliate Network", "create"))
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc(
                {
                    "doctype": "Affiliate Network",
                    "network_name": "TEST-NET-GuestAttempt",
                    "program_type": "Direct",
                    "report_format": "CSV",
                    "status": "Active",
                }
            ).insert()
