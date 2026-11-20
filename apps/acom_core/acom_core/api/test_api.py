"""API, contract, and security tests for Phase 2 (TEST_PLAN.md A1–A6, E6, API_CONTRACTS.md)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate

from acom_core.affiliate_commerce.doctype.affiliate_product.test_affiliate_product import (
    _ensure_category,
)
from acom_core.affiliate_commerce.services.catalog_service import (
    BANNED_PUBLIC_FIELDS,
    assert_no_banned_fields,
)
from acom_core.affiliate_commerce.services.click_service import (
    SESSION_RATE_LIMIT_PER_HOUR,
    record_click,
)
from acom_core.api.affiliate import (
    record_affiliate_click,
    resolve_affiliate_redirect,
    update_affiliate_product_status,
)
from acom_core.api.catalog import get_catalog, get_categories, get_product
from acom_core.api.errors import AcomApiError


def _collect_all_keys(obj) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys.update(_collect_all_keys(v))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            keys.update(_collect_all_keys(item))
    return keys


class TestPhase2ApiAndSecurity(IntegrationTestCase):
    def setUp(self) -> None:
        frappe.set_user("Administrator")
        frappe.local.form_dict = frappe._dict()
        self.category = _ensure_category()

        self.active_net = frappe.get_doc(
            {
                "doctype": "Affiliate Network",
                "network_name": "TEST-API-NET-ACTIVE",
                "program_type": "Marketplace",
                "report_format": "CSV",
                "tracking_param": "tag",
                "status": "Active",
            }
        ).insert()
        self.paused_net = frappe.get_doc(
            {
                "doctype": "Affiliate Network",
                "network_name": "TEST-API-NET-PAUSED",
                "program_type": "Marketplace",
                "report_format": "CSV",
                "tracking_param": "tag",
                "status": "Paused",
            }
        ).insert()

        self.published_product = frappe.get_doc(
            {
                "doctype": "Affiliate Product",
                "product_name": "API Published Steel Bottle 1L",
                "slug": "test-api-published-bottle",
                "product_sku": "B0APIPUB01",
                "marketplace": "Amazon",
                "affiliate_network": self.active_net.name,
                "affiliate_url": "https://www.amazon.in/dp/B0APIPUB01?tag=acom-21",
                "category": self.category,
                "commission_type": "Percentage",
                "commission_rate": 12.5,
                "currency": "INR",
                "display_price": 799,
                "short_description": "Vacuum insulated stainless steel bottle.",
                "pros": [{"text": "Keeps water cold 24h", "sort_order": 1}],
                "cons": [{"text": "Hand wash only", "sort_order": 1}],
                "status": "Published",
                "last_verified_date": nowdate(),
                "content_review_status": "Approved",
                "disclosure_required": 1,
            }
        ).insert()

        self.draft_product = frappe.get_doc(
            {
                "doctype": "Affiliate Product",
                "product_name": "API Draft Secret Item",
                "slug": "test-api-draft-secret",
                "product_sku": "B0APIDRF01",
                "marketplace": "Amazon",
                "affiliate_network": self.active_net.name,
                "affiliate_url": "https://www.amazon.in/dp/B0APIDRF01?tag=acom-21",
                "category": self.category,
                "commission_type": "Percentage",
                "commission_rate": 15.0,
                "currency": "INR",
                "display_price": 1299,
                "status": "Draft",
                "disclosure_required": 1,
            }
        ).insert()

        self.paused_product = frappe.get_doc(
            {
                "doctype": "Affiliate Product",
                "product_name": "API Paused Item",
                "slug": "test-api-paused-item",
                "product_sku": "B0APIPSD01",
                "marketplace": "Amazon",
                "affiliate_network": self.active_net.name,
                "affiliate_url": "https://www.amazon.in/dp/B0APIPSD01?tag=acom-21",
                "category": self.category,
                "commission_type": "Percentage",
                "commission_rate": 10.0,
                "currency": "INR",
                "display_price": 999,
                "status": "Paused",
                "disclosure_required": 1,
            }
        ).insert()

        # Product initially published on an active network that later becomes paused
        self.inactive_net_product = frappe.get_doc(
            {
                "doctype": "Affiliate Product",
                "product_name": "API Inactive Network Item",
                "slug": "test-api-inactive-net-item",
                "product_sku": "B0APIINA01",
                "marketplace": "Amazon",
                "affiliate_network": self.active_net.name,
                "affiliate_url": "https://www.amazon.in/dp/B0APIINA01?tag=acom-21",
                "category": self.category,
                "commission_type": "Percentage",
                "commission_rate": 9.0,
                "currency": "INR",
                "display_price": 599,
                "status": "Published",
                "last_verified_date": nowdate(),
                "content_review_status": "Approved",
                "disclosure_required": 1,
            }
        ).insert()
        # Move it to paused_net at DB level to simulate a network being paused post-publish
        frappe.db.set_value(
            "Affiliate Product",
            self.inactive_net_product.name,
            "affiliate_network",
            self.paused_net.name,
            update_modified=False,
        )

        # Create a non-privileged authenticated user (ACOM Analyst only)
        self.analyst_email = "test_acom_analyst@acom.local"
        if not frappe.db.exists("User", self.analyst_email):
            u = frappe.get_doc(
                {
                    "doctype": "User",
                    "email": self.analyst_email,
                    "first_name": "Test",
                    "last_name": "Analyst",
                    "enabled": 1,
                    "send_welcome_email": 0,
                    "roles": [{"role": "ACOM Analyst"}],
                }
            )
            u.insert(ignore_permissions=True)

    def tearDown(self) -> None:
        frappe.set_user("Administrator")
        frappe.local.form_dict = frappe._dict()
        for prod in (
            self.published_product.name,
            self.draft_product.name,
            self.paused_product.name,
            self.inactive_net_product.name,
        ):
            for clk in frappe.get_all(
                "Affiliate Click", filters={"affiliate_product": prod}, pluck="name"
            ):
                frappe.delete_doc("Affiliate Click", clk, force=True, ignore_permissions=True)
            if frappe.db.exists("Affiliate Product", prod):
                frappe.delete_doc("Affiliate Product", prod, force=True, ignore_permissions=True)
        for net in (self.active_net.name, self.paused_net.name):
            if frappe.db.exists("Affiliate Network", net):
                frappe.delete_doc("Affiliate Network", net, force=True, ignore_permissions=True)
        if frappe.db.exists("User", self.analyst_email):
            frappe.delete_doc("User", self.analyst_email, force=True, ignore_permissions=True)

    def test_A1_guest_reads_public_catalog_and_excludes_non_published_or_inactive_network(self) -> None:
        frappe.set_user("Guest")
        res = get_catalog(page=1, page_size=50, sales_type="AFFILIATE")
        self.assertTrue(res["ok"])
        self.assertIn("correlation_id", res["meta"])

        slugs = [item["slug"] for item in res["data"]["items"]]
        self.assertIn("test-api-published-bottle", slugs)
        self.assertNotIn("test-api-draft-secret", slugs)
        self.assertNotIn("test-api-paused-item", slugs)
        self.assertNotIn("test-api-inactive-net-item", slugs)

        card = next(i for i in res["data"]["items"] if i["slug"] == "test-api-published-bottle")
        self.assertEqual(card["sales_type"], "AFFILIATE")
        self.assertEqual(card["cta_label"], "View Deal")
        self.assertEqual(card["display_price"], {"amount": "799.00", "currency": "INR"})
        self.assertIsInstance(card["display_price"]["amount"], str)

        # Single product detail
        detail = get_product(slug="test-api-published-bottle")
        self.assertTrue(detail["ok"])
        self.assertIs(detail["data"]["disclosure_required"], True)
        self.assertTrue(len(detail["data"]["affiliate_disclosure"]) > 10)
        self.assertEqual(detail["data"]["view_deal_url"], "/api/affiliate/click")
        self.assertEqual(detail["data"]["pros"], ["Keeps water cold 24h"])
        self.assertEqual(detail["data"]["cons"], ["Hand wash only"])

        # Draft, paused, and inactive-network products return 404 (never leak existence)
        for hidden_slug in (
            "test-api-draft-secret",
            "test-api-paused-item",
            "test-api-inactive-net-item",
            "non-existent-sku-slug",
        ):
            missing = get_product(slug=hidden_slug)
            self.assertFalse(missing["ok"])
            self.assertEqual(missing["error"]["code"], "NOT_FOUND")

        # Categories endpoint works for Guest
        cats = get_categories()
        self.assertTrue(cats["ok"])
        self.assertTrue(any(c["name"] == self.category for c in cats["data"]["categories"]))

    def test_A2_guest_cannot_mutate_business_data(self) -> None:
        frappe.set_user("Guest")
        res = update_affiliate_product_status(
            product_name=self.draft_product.name, status="Paused"
        )
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "UNAUTHENTICATED")

        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc("Affiliate Product", self.draft_product.name).save()

    def test_A4_non_privileged_user_gets_403_on_status_mutation(self) -> None:
        frappe.set_user(self.analyst_email)
        res = update_affiliate_product_status(
            product_name=self.draft_product.name, status="Paused"
        )
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "FORBIDDEN")

    def test_A6_public_responses_contain_zero_banned_fields_and_guard_trips_on_leak(self) -> None:
        frappe.set_user("Guest")
        catalog_res = get_catalog(page=1, page_size=50)
        product_res = get_product(slug="test-api-published-bottle")
        categories_res = get_categories()

        for payload in (catalog_res["data"], product_res["data"], categories_res["data"]):
            keys = _collect_all_keys(payload)
            leaked = keys.intersection(BANNED_PUBLIC_FIELDS)
            self.assertEqual(leaked, set(), f"Banned fields leaked: {leaked}")
            # Also ensure raw affiliate URL never appears in any value
            self.assertNotIn("tag=acom-21", str(payload))

        # Negative test: confirm the runtime guard itself blocks any leaked banned key
        for banned_key in ("supplier_cost", "commission_rate", "affiliate_url", "owner"):
            with self.assertRaises(AcomApiError):
                assert_no_banned_fields({"items": [{banned_key: "secret"}]})

    def test_catalog_rejects_unknown_query_params(self) -> None:
        frappe.set_user("Guest")
        frappe.local.form_dict = frappe._dict({"page": 1, "inject_field": "evil"})
        res = get_catalog(page=1)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "VALIDATION_ERROR")

    def test_click_recording_happy_path_and_redirect_resolution(self) -> None:
        frappe.set_user("Guest")
        res = record_affiliate_click(
            product_slug="test-api-published-bottle",
            session_id="s_test_happy_0001",
            source="google",
            medium="organic",
            landing_path="/products/test-api-published-bottle",
            clicked_at="2000-01-01T00:00:00Z",  # must be ignored
        )
        self.assertTrue(res["ok"])
        click_id = res["data"]["click_id"]
        self.assertEqual(str(uuid.UUID(click_id, version=4)), click_id)
        self.assertEqual(res["data"]["redirect_url"], f"/go/{click_id}")

        # Verify persisted click has server timestamp, no PII, coarse UA
        stored = frappe.db.get_value(
            "Affiliate Click",
            click_id,
            ["click_id", "clicked_at", "attribution_status", "user_agent_family"],
            as_dict=True,
        )
        self.assertEqual(stored["attribution_status"], "Recorded")
        self.assertFalse(str(stored["clicked_at"]).startswith("2000-01-01"))

        # Verify redirect resolution appends subid=click_id and preserves tracking param
        redir = resolve_affiliate_redirect(click_id=click_id)
        self.assertTrue(redir["ok"])
        self.assertIn("tag=acom-21", redir["data"]["destination_url"])
        self.assertIn(f"subid={click_id}", redir["data"]["destination_url"])
        self.assertEqual(redir["data"]["rel"], "sponsored nofollow")

    def test_click_rejects_pii_unknown_fields_and_invalid_or_inactive_skus(self) -> None:
        # 1. PII / unknown fields rejected with 400
        for bad_payload in (
            {
                "product_slug": "test-api-published-bottle",
                "session_id": "s_test_pii_0001",
                "email": "user@example.com",
            },
            {
                "product_slug": "test-api-published-bottle",
                "session_id": "s_test_pii_0002",
                "ip_address": "1.2.3.4",
            },
            {
                "product_slug": "test-api-published-bottle",
                "session_id": "s_test_pii_0003",
                "price": "1.00",
            },
        ):
            with self.assertRaises(AcomApiError) as ctx:
                record_click(bad_payload, enforce_rate_limits=False)
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")

        # 2. Non-existent slug -> 404 NOT_FOUND
        with self.assertRaises(AcomApiError) as ctx:
            record_click(
                {"product_slug": "does-not-exist-999", "session_id": "s_test_404_0001"},
                enforce_rate_limits=False,
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

        # 3. Draft, Paused, and Inactive-Network products -> 422 PRODUCT_UNAVAILABLE
        for unavailable_slug in (
            "test-api-draft-secret",
            "test-api-paused-item",
            "test-api-inactive-net-item",
        ):
            with self.assertRaises(AcomApiError) as ctx:
                record_click(
                    {"product_slug": unavailable_slug, "session_id": "s_test_422_0001"},
                    enforce_rate_limits=False,
                )
            self.assertEqual(ctx.exception.status_code, 422)
            self.assertEqual(ctx.exception.code, "PRODUCT_UNAVAILABLE")

    def test_click_deduplication_within_2_seconds_using_injected_clock(self) -> None:
        t0 = frappe.utils.now_datetime()
        session = f"s_dedup_{uuid.uuid4().hex[:12]}"

        first, status1 = record_click(
            {"product_slug": "test-api-published-bottle", "session_id": session},
            now_fn=lambda: t0,
            enforce_rate_limits=False,
        )
        self.assertEqual(status1, 201)

        # Within 2 seconds -> deduplicated, returns same click_id
        second, status2 = record_click(
            {"product_slug": "test-api-published-bottle", "session_id": session},
            now_fn=lambda: t0 + timedelta(seconds=1),
            enforce_rate_limits=False,
        )
        self.assertEqual(status2, 200)
        self.assertEqual(second["click_id"], first["click_id"])

        # After 2 seconds -> new click created
        third, status3 = record_click(
            {"product_slug": "test-api-published-bottle", "session_id": session},
            now_fn=lambda: t0 + timedelta(seconds=5),
            enforce_rate_limits=False,
        )
        self.assertEqual(status3, 201)
        self.assertNotEqual(third["click_id"], first["click_id"])

    def test_click_rate_limiting_returns_429_with_retry_after(self) -> None:
        session = f"s_ratelimit_{uuid.uuid4().hex[:12]}"
        # Seed Redis counter right at the session limit so test runs in milliseconds
        import hashlib

        key = f"acom:rl:click_session:{hashlib.sha256(session.encode()).hexdigest()[:32]}"
        frappe.cache().set_value(key, SESSION_RATE_LIMIT_PER_HOUR, expires_in_sec=60)
        try:
            with self.assertRaises(AcomApiError) as ctx:
                record_click(
                    {"product_slug": "test-api-published-bottle", "session_id": session},
                    enforce_rate_limits=True,
                )
            self.assertEqual(ctx.exception.status_code, 429)
            self.assertEqual(ctx.exception.code, "RATE_LIMITED")
            self.assertIn("Retry-After", ctx.exception.headers)
        finally:
            frappe.cache().delete_value(key)

    def test_E6_deleting_submitted_erpnext_document_is_blocked(self) -> None:
        submitted_so = frappe.db.get_value("Sales Order", {"docstatus": 1}, "name")
        if submitted_so:
            with self.assertRaises(frappe.ValidationError):
                frappe.delete_doc("Sales Order", submitted_so)
