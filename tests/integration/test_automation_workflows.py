"""Integration tests for host-side AutomationRunner connecting to ERPNext with M2M HMAC."""

from __future__ import annotations

import time
import unittest
from automation.workflows.runner import AutomationRunner


class TestHostAutomationWorkflows(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = AutomationRunner()

    def test_runner_inject_event_and_duplicate_handling(self) -> None:
        """Injected event with valid HMAC succeeds; duplicate key returns 409."""
        idem_key = f"host_test_idem_{int(time.time())}"
        payload = {"source": "HostTest", "action": "ping"}

        res1 = self.runner.inject_event(
            event_type="test.host_ping",
            idempotency_key=idem_key,
            payload=payload,
            source="Agent",
        )
        self.assertTrue(res1.get("ok"), f"Failed: {res1}")
        self.assertEqual(res1.get("data", {}).get("processing_status"), "Received")

        # Second submission with same idempotency key
        res2 = self.runner.inject_event(
            event_type="test.host_ping",
            idempotency_key=idem_key,
            payload=payload,
            source="Agent",
        )
        self.assertFalse(res2.get("ok"))
        self.assertEqual(res2.get("error", {}).get("code"), "DUPLICATE_EVENT")

    def test_runner_trigger_workflow_product_research(self) -> None:
        """Host runner triggers product research workflow via HMAC."""
        res = self.runner.trigger_workflow(
            "product_research",
            {
                "keyword": "Stainless Steel Bento Box",
                "category": "Home & Kitchen",
                "supplier_cost": 250.0,
                "estimated_retail_price": 600.0,
                "min_target_margin_pct": 20.0,
            },
        )
        self.assertTrue(res.get("ok"), f"Failed: {res}")
        self.assertTrue(res.get("data", {}).get("viable"))
        self.assertIn("approval_request_id", res.get("data", {}))

    def test_runner_hmac_tampered_request_rejected(self) -> None:
        """Runner with bad HMAC secret gets rejected with HTTP 401/403."""
        bad_runner = AutomationRunner(hmac_secret="bad-attacker-hmac-secret")
        res = bad_runner.inject_event(
            event_type="test.unauthorized",
            idempotency_key=f"bad_sig_{int(time.time())}",
            payload={},
        )
        self.assertFalse(res.get("ok"))
        err_code = res.get("error", {}).get("code")
        self.assertTrue(err_code in ("INVALID_SIGNATURE", "UNAUTHORIZED", "HTTP_401", "HTTP_403"))
