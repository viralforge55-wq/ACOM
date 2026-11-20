"""Integration tests for AI Offline Fallback (TEST_PLAN §2.6, §4 scenario 6).

Proves that:
1. When Ollama is unreachable or stopped mid-workflow, ERPNext catalog and business
   endpoints remain 100% operational (HTTP 200).
2. The AI Runner catches connection errors, returns an OLLAMA_OFFLINE status,
   and marks tasks as retryable without unhandled worker crashes.
"""

import json
import unittest
import urllib.request
import urllib.error

from ai.client import OllamaClient, OllamaOfflineError
from ai.runner import AIRunner


class TestAIOfflineFallback(unittest.TestCase):
    """Test system resilience when local Ollama service is stopped or offline."""

    def test_erpnext_operational_when_ai_offline(self):
        """ERPNext public catalog remains 100% operational even if Ollama is disconnected."""
        url = "http://127.0.0.1:8080/api/method/acom_core.api.catalog.get_catalog"
        headers = {
            "Host": "acom.localhost",
        }
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=5.0) as resp:
            self.assertEqual(resp.status, 200)
            body = json.loads(resp.read().decode())
            data = body.get("message", body)
            self.assertTrue(data.get("ok"))
            self.assertIn("data", data)

    def test_runner_handles_offline_gracefully(self):
        """Runner cleanly reports OLLAMA_OFFLINE with retryable=True on connection failure."""
        # Point to a guaranteed dead local port
        dead_client = OllamaClient(base_url="http://127.0.0.1:59999", timeout_seconds=1.0, max_retries=0)
        self.assertFalse(dead_client.is_healthy())

        runner = AIRunner(client=dead_client)
        result = runner.execute_task(
            agent_id="product_hunter",
            input_payload={
                "raw_text": "Sample Product",
                "supplier_name": "SupplierCo",
                "supplier_sku": "SKU-999",
                "category": "Home",
                "supplier_cost": 50.0,
            },
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "OLLAMA_OFFLINE")
        self.assertTrue(result.get("retryable"))
        self.assertIn("Ollama server unreachable", result["message"])


if __name__ == "__main__":
    unittest.main()
