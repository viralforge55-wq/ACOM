"""Comprehensive Phase 4 tests: Affiliate Conversion, Import Batch & Reconciliation.

Covers TEST_PLAN.md F3–F8, I5, status transition state machine, orphan subid handling,
Decimal precision, bot exclusion, payout variance, Desk Script Report, and role/403 security.
"""

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from acom_core.affiliate_commerce.doctype.affiliate_product.test_affiliate_product import (
    _ensure_category,
)
from acom_core.affiliate_commerce.report.affiliate_commission_reconciliation.affiliate_commission_reconciliation import (
    execute as execute_reconciliation_report,
)
from acom_core.api.reconciliation import (
    get_affiliate_reconciliation,
    import_affiliate_report,
    resolve_orphan_conversion,
)

IGNORE_TEST_RECORD_DEPENDENCIES = [
    "Affiliate Network",
    "Affiliate Product",
    "Affiliate Click",
    "Affiliate Campaign",
    "Affiliate Import Batch",
    "Currency",
    "Item Group",
]


class TestAffiliateConversionAndReconciliation(IntegrationTestCase):
    def setUp(self) -> None:
        frappe.set_user("Administrator")
        frappe.local.form_dict = frappe._dict()
        category = _ensure_category()

        self.network = frappe.get_doc(
            {
                "doctype": "Affiliate Network",
                "network_name": "TEST-P4-NET",
                "program_type": "Marketplace",
                "report_format": "CSV",
                "tracking_param": "tag",
                "cookie_window_days": 7,
                "status": "Active",
            }
        ).insert()

        self.campaign = frappe.get_doc(
            {
                "doctype": "Affiliate Campaign",
                "campaign_name": "TEST-P4-CAMP",
                "affiliate_network": self.network.name,
                "status": "Active",
            }
        ).insert()

        self.product = frappe.get_doc(
            {
                "doctype": "Affiliate Product",
                "product_name": "Phase 4 Test Bottle",
                "slug": "test-p4-bottle",
                "product_sku": "B0P4TEST01",
                "marketplace": "Amazon",
                "affiliate_network": self.network.name,
                "affiliate_url": "https://www.amazon.in/dp/B0P4TEST01?tag=acom-21",
                "category": category,
                "campaign": self.campaign.name,
                "commission_type": "Percentage",
                "commission_rate": 10.0,
                "currency": "INR",
                "display_price": 1000,
                "status": "Published",
                "last_verified_date": nowdate(),
                "content_review_status": "Approved",
                "disclosure_required": 1,
            }
        ).insert()

        self.click = frappe.get_doc(
            {
                "doctype": "Affiliate Click",
                "affiliate_product": self.product.name,
                "session_id": "s_p4_valid_session_01",
                "source": "google",
                "medium": "organic",
                "landing_path": "/products/test-p4-bottle",
                "user_agent_family": "Chrome",
                "is_bot_suspected": 0,
            }
        ).insert()

        self.bot_click = frappe.get_doc(
            {
                "doctype": "Affiliate Click",
                "affiliate_product": self.product.name,
                "session_id": "s_p4_bot_session_01",
                "source": "other",
                "user_agent_family": "Bot",
                "is_bot_suspected": 1,
            }
        ).insert()

        self.analyst_user = "test_p4_analyst@acom.local"
        if not frappe.db.exists("User", self.analyst_user):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": self.analyst_user,
                    "first_name": "P4",
                    "last_name": "Analyst",
                    "enabled": 1,
                    "send_welcome_email": 0,
                    "roles": [{"role": "ACOM Analyst"}],
                }
            ).insert(ignore_permissions=True)

        self.finance_user = "test_p4_finance@acom.local"
        if not frappe.db.exists("User", self.finance_user):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": self.finance_user,
                    "first_name": "P4",
                    "last_name": "Finance",
                    "enabled": 1,
                    "send_welcome_email": 0,
                    "roles": [{"role": "ACOM Finance"}],
                }
            ).insert(ignore_permissions=True)

    def tearDown(self) -> None:
        frappe.set_user("Administrator")
        frappe.local.form_dict = frappe._dict()
        # Delete reversals first (FK to original conversion)
        for name in frappe.get_all(
            "Affiliate Conversion",
            filters={"affiliate_network": self.network.name, "reversed_conversion": ["is", "set"]},
            pluck="name",
        ):
            frappe.delete_doc("Affiliate Conversion", name, force=True, ignore_permissions=True)
        for name in frappe.get_all(
            "Affiliate Conversion",
            filters={"affiliate_network": self.network.name},
            pluck="name",
        ):
            frappe.delete_doc("Affiliate Conversion", name, force=True, ignore_permissions=True)
        for name in frappe.get_all(
            "Affiliate Import Batch",
            filters={"affiliate_network": self.network.name},
            pluck="name",
        ):
            frappe.delete_doc("Affiliate Import Batch", name, force=True, ignore_permissions=True)
        for name in frappe.get_all(
            "Affiliate Click",
            filters={"affiliate_product": self.product.name},
            pluck="name",
        ):
            frappe.delete_doc("Affiliate Click", name, force=True, ignore_permissions=True)
        for dt, docname in (
            ("Affiliate Product", self.product.name),
            ("Affiliate Campaign", self.campaign.name),
            ("Affiliate Network", self.network.name),
            ("User", self.analyst_user),
            ("User", self.finance_user),
        ):
            if frappe.db.exists(dt, docname):
                frappe.delete_doc(dt, docname, force=True, ignore_permissions=True)

    def test_F3_F4_I5_csv_import_attribution_and_duplicate_idempotency(self) -> None:
        csv_body = (
            "external_transaction_id,external_order_id,conversion_date,order_value,commission_amount,status,subid,currency\n"
            f"TXN-P4-001,ORD-101,{nowdate()},1000.00,95.50,PENDING,{self.click.click_id},INR\n"
        )

        # First import -> inserted=1, Pending, click matched
        r1 = import_affiliate_report(
            network=self.network.name,
            report_date=nowdate(),
            csv_content=csv_body,
            file_name="demo_report_1.csv",
        )
        self.assertTrue(r1["ok"])
        self.assertEqual(r1["data"]["inserted"], 1)
        self.assertEqual(r1["data"]["skipped"], 0)
        self.assertEqual(r1["data"]["unmatched"], 0)

        conv_name = r1["data"]["conversion_ids"][0]
        conv = frappe.get_doc("Affiliate Conversion", conv_name)
        self.assertEqual(conv.affiliate_click, self.click.name)
        self.assertEqual(conv.affiliate_product, self.product.name)
        self.assertEqual(conv.campaign, self.campaign.name)
        self.assertEqual(conv.matched_by, "SubId")
        self.assertEqual(conv.commission_status, "Pending")
        self.assertEqual(len(conv.status_history), 1)

        # Click status updated to Matched
        self.assertEqual(
            frappe.db.get_value("Affiliate Click", self.click.name, "attribution_status"),
            "Matched",
        )

        # Re-importing the exact same CSV -> skipped=1, no duplicate row (F4 / I5)
        r2 = import_affiliate_report(
            network=self.network.name,
            report_date=nowdate(),
            csv_content=csv_body,
            file_name="demo_report_1.csv",
        )
        self.assertTrue(r2["ok"])
        self.assertEqual(r2["data"]["inserted"], 0)
        self.assertEqual(r2["data"]["updated"], 0)
        self.assertEqual(r2["data"]["skipped"], 1)
        self.assertEqual(
            frappe.db.count("Affiliate Conversion", {"affiliate_network": self.network.name}),
            1,
        )

    def test_F5_F6_F7_revenue_separation_lifecycle_and_reversal(self) -> None:
        today = nowdate()
        # 1. Import 2 Pending conversions
        r1 = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[
                {
                    "network_conversion_id": "TXN-REV-1",
                    "conversion_date": today,
                    "order_value": "1000.00",
                    "commission_amount": "100.00",
                    "commission_status": "PENDING",
                    "subid": self.click.click_id,
                },
                {
                    "network_conversion_id": "TXN-REV-2",
                    "conversion_date": today,
                    "order_value": "500.00",
                    "commission_amount": "45.25",
                    "commission_status": "PENDING",
                    "product_sku": "B0P4TEST01",
                },
            ],
        )
        self.assertTrue(r1["ok"])
        self.assertEqual(r1["data"]["inserted"], 2)

        # F5: Pending is NEVER revenue; bot click excluded from valid clicks
        recon1 = get_affiliate_reconciliation(affiliate_network=self.network.name)
        self.assertTrue(recon1["ok"])
        self.assertEqual(recon1["data"]["clicks"]["total_valid_clicks"], 1)
        self.assertEqual(recon1["data"]["clicks"]["bot_clicks_excluded"], 1)
        self.assertEqual(recon1["data"]["commissions"]["pending"]["amount"], "145.25")
        self.assertEqual(recon1["data"]["commissions"]["confirmed_revenue"]["amount"], "0.00")
        self.assertEqual(recon1["data"]["commissions"]["realized_revenue"]["amount"], "0.00")

        # F6: Confirmation report moves TXN-REV-1 -> Confirmed (via "APPROVED" synonym)
        r2 = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[
                {
                    "network_conversion_id": "TXN-REV-1",
                    "conversion_date": today,
                    "commission_amount": "100.00",
                    "commission_status": "APPROVED",
                }
            ],
        )
        self.assertTrue(r2["ok"])
        self.assertEqual(r2["data"]["updated"], 1)

        recon2 = get_affiliate_reconciliation(affiliate_network=self.network.name)
        self.assertEqual(recon2["data"]["commissions"]["pending"]["amount"], "45.25")
        self.assertEqual(recon2["data"]["commissions"]["confirmed"]["amount"], "100.00")
        self.assertEqual(recon2["data"]["commissions"]["confirmed_revenue"]["amount"], "100.00")
        self.assertEqual(recon2["data"]["commissions"]["realized_revenue"]["amount"], "0.00")

        # Payout report moves TXN-REV-1 -> Paid with payment_reference
        r3 = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[
                {
                    "network_conversion_id": "TXN-REV-1",
                    "conversion_date": today,
                    "commission_amount": "100.00",
                    "commission_status": "PAID",
                    "payment_reference": "UTR-2026-998877",
                }
            ],
        )
        self.assertTrue(r3["ok"])
        self.assertEqual(r3["data"]["updated"], 1)

        # Verify audit trail has 3 entries: Pending -> Confirmed -> Paid
        conv_doc = frappe.get_doc(
            "Affiliate Conversion",
            {"affiliate_network": self.network.name, "network_conversion_id": "TXN-REV-1"},
        )
        self.assertEqual(len(conv_doc.status_history), 3)
        self.assertEqual(
            [h.to_status for h in conv_doc.status_history],
            ["Pending", "Confirmed", "Paid"],
        )

        # Payout reconciliation check: exact match vs mismatch
        recon_match = get_affiliate_reconciliation(
            affiliate_network=self.network.name, payout_expected="100.00"
        )
        self.assertFalse(recon_match["data"]["payout_check"]["has_exception"])
        recon_mismatch = get_affiliate_reconciliation(
            affiliate_network=self.network.name, payout_expected="120.00"
        )
        self.assertTrue(recon_mismatch["data"]["payout_check"]["has_exception"])
        self.assertEqual(recon_mismatch["data"]["payout_check"]["variance"]["amount"], "-20.00")

        # F7: Reversal creates a NEW row, retains original row, reduces confirmed revenue
        r4 = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[
                {
                    "network_conversion_id": "TXN-REV-1",
                    "conversion_date": today,
                    "commission_amount": "30.00",
                    "commission_status": "REVERSED",
                    "reversal_reason": "Partial customer return on marketplace",
                }
            ],
        )
        self.assertTrue(r4["ok"])
        self.assertEqual(r4["data"]["inserted"], 1)
        # Re-importing the same reversal is idempotent
        r4_dup = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[
                {
                    "network_conversion_id": "TXN-REV-1",
                    "conversion_date": today,
                    "commission_amount": "30.00",
                    "commission_status": "REVERSED",
                    "reversal_reason": "Partial customer return on marketplace",
                }
            ],
        )
        self.assertTrue(r4_dup["ok"])
        self.assertEqual(r4_dup["data"]["skipped"], 1)

        # Original TXN-REV-1 is retained untouched as Paid
        self.assertEqual(
            frappe.db.get_value("Affiliate Conversion", conv_doc.name, "commission_status"),
            "Paid",
        )
        recon3 = get_affiliate_reconciliation(affiliate_network=self.network.name)
        self.assertEqual(recon3["data"]["commissions"]["reversed"]["amount"], "30.00")
        self.assertEqual(recon3["data"]["commissions"]["confirmed_revenue"]["amount"], "70.00")

    def test_illegal_status_transitions_rejected(self) -> None:
        today = nowdate()
        # Create a Rejected conversion
        res = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[
                {
                    "network_conversion_id": "TXN-REJ-1",
                    "conversion_date": today,
                    "commission_amount": "50.00",
                    "commission_status": "REJECTED",
                }
            ],
        )
        self.assertTrue(res["ok"])

        # Rejected -> Paid MUST be rejected
        illegal_paid = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[
                {
                    "network_conversion_id": "TXN-REJ-1",
                    "conversion_date": today,
                    "commission_amount": "50.00",
                    "commission_status": "PAID",
                    "payment_reference": "UTR-ILLEGAL",
                }
            ],
        )
        self.assertFalse(illegal_paid["ok"])
        self.assertEqual(illegal_paid["error"]["code"], "ILLEGAL_STATUS_TRANSITION")

        # Rejected -> Confirmed MUST be rejected
        illegal_conf = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[
                {
                    "network_conversion_id": "TXN-REJ-1",
                    "conversion_date": today,
                    "commission_amount": "50.00",
                    "commission_status": "CONFIRMED",
                }
            ],
        )
        self.assertFalse(illegal_conf["ok"])
        self.assertEqual(illegal_conf["error"]["code"], "ILLEGAL_STATUS_TRANSITION")

        # Pending -> Paid directly (skipping Confirmed) MUST be rejected
        import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[
                {
                    "network_conversion_id": "TXN-SKIP-1",
                    "conversion_date": today,
                    "commission_amount": "25.00",
                    "commission_status": "PENDING",
                }
            ],
        )
        illegal_skip = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[
                {
                    "network_conversion_id": "TXN-SKIP-1",
                    "conversion_date": today,
                    "commission_amount": "25.00",
                    "commission_status": "PAID",
                    "payment_reference": "UTR-SKIP",
                }
            ],
        )
        self.assertFalse(illegal_skip["ok"])
        self.assertEqual(illegal_skip["error"]["code"], "ILLEGAL_STATUS_TRANSITION")

    def test_F8_orphan_subid_flagged_for_manual_review_and_resolvable(self) -> None:
        today = nowdate()
        res = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[
                {
                    "network_conversion_id": "TXN-ORPHAN-1",
                    "conversion_date": today,
                    "commission_amount": "42.00",
                    "commission_status": "PENDING",
                    "subid": "00000000-0000-4000-8000-000000000999",
                }
            ],
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["data"]["inserted"], 1)
        self.assertEqual(res["data"]["unmatched"], 1)

        conv_id = res["data"]["conversion_ids"][0]
        recon = get_affiliate_reconciliation(affiliate_network=self.network.name)
        self.assertEqual(recon["data"]["conversions"]["unmatched_conversions"], 1)
        self.assertEqual(len(recon["data"]["manual_review_queue"]), 1)
        self.assertEqual(
            recon["data"]["manual_review_queue"][0]["raw_subid"],
            "00000000-0000-4000-8000-000000000999",
        )

        # Resolve manually
        resolved = resolve_orphan_conversion(
            conversion_name=conv_id,
            affiliate_product=self.product.name,
            note="Matched against Amazon SKU report",
        )
        self.assertTrue(resolved["ok"])
        self.assertEqual(resolved["data"]["matched_by"], "Manual")
        self.assertFalse(resolved["data"]["needs_manual_review"])

        recon_after = get_affiliate_reconciliation(affiliate_network=self.network.name)
        self.assertEqual(recon_after["data"]["conversions"]["unmatched_conversions"], 0)
        self.assertEqual(recon_after["data"]["conversions"]["attributed_conversions"], 1)

    def test_negative_malformed_amounts_and_csv_schema_mismatch_rejected_atomically(self) -> None:
        today = nowdate()
        # Negative commission
        neg = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[
                {
                    "network_conversion_id": "TXN-GOOD-0",
                    "conversion_date": today,
                    "commission_amount": "10.00",
                },
                {
                    "network_conversion_id": "TXN-NEG-1",
                    "conversion_date": today,
                    "commission_amount": "-5.00",
                },
            ],
        )
        self.assertFalse(neg["ok"])
        self.assertEqual(neg["error"]["code"], "VALIDATION_ERROR")
        # Atomic: zero partial writes (TXN-GOOD-0 was NOT inserted)
        self.assertEqual(
            frappe.db.count("Affiliate Conversion", {"affiliate_network": self.network.name}),
            0,
        )

        # Malformed string commission
        bad_str = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[
                {
                    "network_conversion_id": "TXN-BAD-1",
                    "conversion_date": today,
                    "commission_amount": "abc",
                }
            ],
        )
        self.assertFalse(bad_str["ok"])
        self.assertEqual(bad_str["error"]["code"], "VALIDATION_ERROR")

        # CSV column mismatch
        bad_csv = "wrong_col_1,wrong_col_2\nval1,val2\n"
        csv_err = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            csv_content=bad_csv,
        )
        self.assertFalse(csv_err["ok"])
        self.assertEqual(csv_err["error"]["code"], "VALIDATION_ERROR")

    def test_exact_decimal_precision_no_float_drift_and_desk_report(self) -> None:
        today = nowdate()
        res = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[
                {"network_conversion_id": "TXN-DEC-1", "conversion_date": today, "commission_amount": "0.10", "commission_status": "CONFIRMED"},
                {"network_conversion_id": "TXN-DEC-2", "conversion_date": today, "commission_amount": "0.20", "commission_status": "CONFIRMED"},
                {"network_conversion_id": "TXN-DEC-3", "conversion_date": today, "commission_amount": "0.30", "commission_status": "CONFIRMED"},
            ],
        )
        self.assertTrue(res["ok"])
        recon = get_affiliate_reconciliation(affiliate_network=self.network.name)
        self.assertEqual(recon["data"]["commissions"]["confirmed"]["amount"], "0.60")
        self.assertEqual(recon["data"]["commissions"]["confirmed_revenue"]["amount"], "0.60")

        # Native ERPNext Desk Script Report executes cleanly
        columns, rows, _, _, summary = execute_reconciliation_report(
            {"affiliate_network": self.network.name}
        )
        self.assertEqual(len(rows), 3)
        self.assertTrue(len(columns) >= 8)
        self.assertTrue(any(s["label"] == "Confirmed Revenue" and s["value"] == 0.6 for s in summary))

    def test_cookie_window_expiry_marks_click_expired(self) -> None:
        future_date = add_days(nowdate(), 30)  # network cookie_window_days is 7
        res = import_affiliate_report(
            network=self.network.name,
            report_date=future_date,
            rows=[
                {
                    "network_conversion_id": "TXN-EXP-1",
                    "conversion_date": future_date,
                    "commission_amount": "20.00",
                    "subid": self.click.click_id,
                }
            ],
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["data"]["unmatched"], 1)
        self.assertEqual(
            frappe.db.get_value("Affiliate Click", self.click.name, "attribution_status"),
            "Expired",
        )

    def test_guest_and_unauthorized_roles_rejected_while_finance_permitted(self) -> None:
        today = nowdate()
        # 1. Guest denied on DocTypes and APIs
        frappe.set_user("Guest")
        self.assertFalse(frappe.has_permission("Affiliate Conversion", "read"))
        self.assertFalse(frappe.has_permission("Affiliate Conversion", "create"))
        self.assertFalse(frappe.has_permission("Affiliate Import Batch", "read"))

        g_imp = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[{"network_conversion_id": "TXN-G", "conversion_date": today, "commission_amount": "10"}],
        )
        self.assertFalse(g_imp["ok"])
        self.assertEqual(g_imp["error"]["code"], "UNAUTHENTICATED")

        g_rec = get_affiliate_reconciliation(affiliate_network=self.network.name)
        self.assertFalse(g_rec["ok"])
        self.assertEqual(g_rec["error"]["code"], "UNAUTHENTICATED")

        # 2. ACOM Analyst: can read reconciliation, CANNOT import (403 FORBIDDEN)
        frappe.set_user(self.analyst_user)
        a_imp = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[{"network_conversion_id": "TXN-A", "conversion_date": today, "commission_amount": "10"}],
        )
        self.assertFalse(a_imp["ok"])
        self.assertEqual(a_imp["error"]["code"], "FORBIDDEN")

        a_rec = get_affiliate_reconciliation(affiliate_network=self.network.name)
        self.assertTrue(a_rec["ok"])

        # 3. ACOM Finance: permitted to import and reconcile
        frappe.set_user(self.finance_user)
        f_imp = import_affiliate_report(
            network=self.network.name,
            report_date=today,
            rows=[{"network_conversion_id": "TXN-FIN-1", "conversion_date": today, "commission_amount": "15.50"}],
        )
        self.assertTrue(f_imp["ok"])
        self.assertEqual(f_imp["data"]["inserted"], 1)
