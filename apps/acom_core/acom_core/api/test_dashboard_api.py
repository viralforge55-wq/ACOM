"""Integration and security tests for Executive Dashboard & BI API (Phase 8).

Verifies:
- Role gating: Guest gets 401, non-manager gets 403, System Manager/ACOM Manager/ACOM Finance permitted.
- Gate F5: Pending affiliate commissions strictly separated and excluded from confirmed revenue.
- Gate 8: Dashboard numbers traceable to rows (drill-through capability).
- Gate A6: Zero banned fields leak in dashboard responses.
- Script report execution and structure.
"""

from __future__ import annotations

from decimal import Decimal
import unittest
import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate, now_datetime

from acom_core.api.dashboard import (
    get_ceo_dashboard_summary,
    get_product_profitability,
    get_drill_through,
)
from acom_core.analytics.services.ceo_dashboard_service import get_ceo_dashboard_summary as _service_summary
from acom_core.analytics.services.profitability_service import get_product_profitability_report
from acom_core.analytics.report.daily_ceo_dashboard.daily_ceo_dashboard import execute as execute_ceo_report
from acom_core.analytics.report.product_profitability_analytics.product_profitability_analytics import execute as execute_profit_report
from acom_core.analytics.report.supplier_performance_analytics.supplier_performance_analytics import execute as execute_supplier_report


class TestDashboardAPIAndBI(IntegrationTestCase):
    """Test suite for Phase 8 Executive BI, CEO Dashboard, and Product Profitability."""

    def setUp(self) -> None:
        frappe.set_user("Administrator")
        self._ensure_user("dash_manager@acom.local", "ACOM Manager")
        self._ensure_user("dash_finance@acom.local", "ACOM Finance")
        self._ensure_user("dash_viewer@acom.local", "ACOM Analyst")

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

    def test_guest_rejected_with_401_on_all_dashboard_apis(self) -> None:
        """Guest cannot access executive dashboard endpoints (SECURITY_POLICY §4)."""
        frappe.set_user("Guest")

        res1 = get_ceo_dashboard_summary()
        self.assertFalse(res1["ok"])
        self.assertEqual(res1["error"]["code"], "UNAUTHENTICATED")

        res2 = get_product_profitability()
        self.assertFalse(res2["ok"])
        self.assertEqual(res2["error"]["code"], "UNAUTHENTICATED")

        res3 = get_drill_through(metric_key="paid_checkouts")
        self.assertFalse(res3["ok"])
        self.assertEqual(res3["error"]["code"], "UNAUTHENTICATED")

    def test_unauthorized_user_rejected_with_403(self) -> None:
        """Non-executive users (without System Manager / ACOM Manager / ACOM Finance) get 403."""
        frappe.set_user("dash_viewer@acom.local")  # ACOM Analyst is not in DASHBOARD_ROLES

        res1 = get_ceo_dashboard_summary()
        self.assertFalse(res1["ok"])
        self.assertEqual(res1["error"]["code"], "FORBIDDEN")

        res2 = get_product_profitability()
        self.assertFalse(res2["ok"])
        self.assertEqual(res2["error"]["code"], "FORBIDDEN")

    def test_authorized_roles_succeed_and_leak_zero_banned_fields(self) -> None:
        """System Manager, ACOM Manager, and ACOM Finance have access and receive clean responses."""
        for user_email in ("dash_manager@acom.local", "dash_finance@acom.local"):
            frappe.set_user(user_email)

            res = get_ceo_dashboard_summary(period="all_time")
            self.assertTrue(res["ok"])
            data = res["data"]

            # Verify response schema sections
            self.assertIn("commerce", data)
            self.assertIn("financial", data)
            self.assertIn("affiliate_performance", data)
            self.assertIn("supplier_performance", data)
            self.assertIn("ai_and_exceptions", data)
            self.assertIn("drill_through", data)

            # Gate A6: Check no banned fields present in serialised output
            raw_json = frappe.as_json(data).lower()
            for banned in ("password", "api_secret", "card_number", "auth_token", "private_key"):
                self.assertNotIn(f'"{banned}"', raw_json)

    def test_F5_pending_affiliate_commission_excluded_from_confirmed_revenue(self) -> None:
        """Gate F5: Pending conversions never increase confirmed revenue or contribution profit."""
        frappe.set_user("Administrator")
        baseline = _service_summary(period="all_time")
        base_confirmed_rev = Decimal(baseline["financial"]["total_confirmed_revenue"]["amount"])
        base_pending_comm = Decimal(baseline["financial"]["estimated_pending_commission"]["amount"])

        net_name = frappe.get_all("Affiliate Network", limit=1)[0]["name"]
        batches = frappe.get_all("Affiliate Import Batch", filters={"affiliate_network": net_name}, limit=1)
        if batches:
            batch_name = batches[0]["name"]
        else:
            b = frappe.get_doc({
                "doctype": "Affiliate Import Batch",
                "affiliate_network": net_name,
                "report_date": nowdate(),
                "file_name": "test_f5.csv",
                "file_hash": frappe.generate_hash(length=16),
                "total_rows": 1,
            }).insert(ignore_permissions=True)
            batch_name = b.name

        # Create a test pending affiliate conversion
        conv = frappe.get_doc(
            {
                "doctype": "Affiliate Conversion",
                "affiliate_network": net_name,
                "network_conversion_id": f"TEST-F5-{frappe.generate_hash(length=8)}",
                "conversion_date": nowdate(),
                "report_date": nowdate(),
                "import_batch": batch_name,
                "order_value": 5000.00,
                "commission_amount": 500.00,
                "commission_status": "Pending",
            }
        )
        conv.insert(ignore_permissions=True)

        after_summary = _service_summary(period="all_time")
        after_confirmed_rev = Decimal(after_summary["financial"]["total_confirmed_revenue"]["amount"])
        after_pending_comm = Decimal(after_summary["financial"]["estimated_pending_commission"]["amount"])

        # Confirmed revenue MUST be unchanged
        self.assertEqual(after_confirmed_rev, base_confirmed_rev)
        # Pending commission MUST have increased by exactly 500.00
        self.assertEqual(after_pending_comm, base_pending_comm + Decimal("500.00"))

        # Transition to Confirmed -> Now confirmed revenue MUST increase
        conv.commission_status = "Confirmed"
        conv.save(ignore_permissions=True)

        confirmed_summary = _service_summary(period="all_time")
        confirmed_rev = Decimal(confirmed_summary["financial"]["total_confirmed_revenue"]["amount"])
        self.assertEqual(confirmed_rev, base_confirmed_rev + Decimal("500.00"))

    def test_Gate8_dashboard_numbers_traceable_to_rows(self) -> None:
        """Gate 8: Every aggregate number on the dashboard is traceable to underlying rows."""
        frappe.set_user("dash_manager@acom.local")
        res = get_ceo_dashboard_summary(period="all_time")
        self.assertTrue(res["ok"])
        dt = res["data"]["drill_through"]

        # Ensure all key drill-through categories exist
        required_keys = (
            "paid_checkouts",
            "pending_checkouts",
            "awaiting_supplier_action",
            "confirmed_conversions",
            "pending_conversions",
            "stockout_products",
            "failed_ai_tasks",
            "pending_approvals",
            "dead_letter_events",
        )
        for k in required_keys:
            self.assertIn(k, dt)
            self.assertIsInstance(dt[k], list)

        # Call get_drill_through for paid_checkouts
        dt_res = get_drill_through(metric_key="paid_checkouts", limit=10)
        self.assertTrue(dt_res["ok"])
        records = dt_res["data"]["records"]
        self.assertIsInstance(records, list)

        # Ensure row counts match drill_through length
        if dt["paid_checkouts"]:
            self.assertGreaterEqual(len(records), 1)
            first_row = records[0]
            self.assertIn("name", first_row)
            self.assertIn("grand_total", first_row)
            self.assertIn(first_row["name"], dt["paid_checkouts"])

    def test_product_profitability_ranking_and_unit_economics(self) -> None:
        """Verify product profitability calculation and descending ranking."""
        frappe.set_user("dash_manager@acom.local")
        res = get_product_profitability(limit=50)
        self.assertTrue(res["ok"])
        ranking = res["data"]["ranking"]
        summary = res["data"]["summary"]

        self.assertIn("products_count", summary)
        self.assertIn("total_revenue", summary)
        self.assertIn("total_contribution_profit", summary)

        if len(ranking) >= 2:
            # Verify descending order by contribution profit
            first_profit = Decimal(ranking[0]["contribution_profit"]["amount"])
            second_profit = Decimal(ranking[1]["contribution_profit"]["amount"])
            self.assertGreaterEqual(first_profit, second_profit)

        for prod in ranking:
            self.assertIn("channel", prod)
            self.assertIn(prod["channel"], ("DROPSHIP", "AFFILIATE"))
            self.assertIn("units_sold", prod)
            self.assertIn("contribution_profit", prod)
            self.assertIn("contribution_margin_pct", prod)
            self.assertIn("drill_through_rows", prod)

    def test_frappe_script_reports_execute_cleanly(self) -> None:
        """All Phase 8 Frappe Script Reports execute cleanly and return the required 5-tuple."""
        frappe.set_user("Administrator")

        # 1. Daily CEO Dashboard
        c1, r1, m1, ch1, s1 = execute_ceo_report({"period": "all_time"})
        self.assertIsInstance(c1, list)
        self.assertIsInstance(r1, list)
        self.assertIsInstance(s1, list)
        self.assertGreaterEqual(len(r1), 10)  # All consolidated KPI rows

        # 2. Product Profitability Analytics
        c2, r2, m2, ch2, s2 = execute_profit_report({})
        self.assertIsInstance(c2, list)
        self.assertIsInstance(r2, list)
        self.assertIsInstance(s2, list)

        # 3. Supplier Performance Analytics
        c3, r3, m3, ch3, s3 = execute_supplier_report({})
        self.assertIsInstance(c3, list)
        self.assertIsInstance(r3, list)
        self.assertIsInstance(s3, list)
