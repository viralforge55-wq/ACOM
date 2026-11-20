"""Unit tests for AI Runner, OllamaClient, and AI Agents."""

import json
import threading
import time
import unittest
from decimal import Decimal

from ai.client import (
    OllamaClient,
    OllamaOfflineError,
    OllamaTimeoutError,
    SchemaValidationError,
    _CONCURRENCY_SEMAPHORE,
)
from ai.schemas.product_hunter import ProductHunterInput, ProductHunterOutput
from ai.schemas.listing_content import ListingContentInput, ListingContentOutput
from ai.agents.product_hunter import ProductHunterAgent
from ai.agents.listing_content import ListingContentAgent
from ai.runner import AIRunner


class TestOllamaClientAndConcurrency(unittest.TestCase):
    """Test client concurrency semaphore, timeouts, retries, and schema parsing."""

    def test_mock_generate_success(self):
        def mock_handler(prompt, system_prompt):
            return json.dumps({
                "product_name": "Test Bamboo Spoon",
                "category": "Kitchen",
                "supplier_name": "BambooCo",
                "supplier_sku": "BAM-01",
                "supplier_price": "100.00",
                "competitor_price": "299.00",
                "proposed_selling_price": "249.00",
                "estimated_shipping_cost": "50.00",
                "estimated_return_rate": 0.03,
                "target_customer": "Kitchen lovers",
                "key_features": ["Eco-friendly", "Reusable"],
                "verdict": "RECOMMENDED",
                "reasoning": "Solid margins and low return rate.",
            })

        client = OllamaClient(mock_handler=mock_handler)
        data, pt, ct = client.generate(
            prompt="analyze bamboo spoon",
            schema_model=ProductHunterOutput,
        )
        self.assertEqual(data["product_name"], "Test Bamboo Spoon")
        self.assertEqual(data["verdict"], "RECOMMENDED")
        self.assertGreater(pt, 0)
        self.assertGreater(ct, 0)

    def test_concurrency_gate_enforced(self):
        """Enforce AI_MAX_CONCURRENT_TASKS=1 via semaphore (ADR-0004)."""
        active_calls = []
        max_seen = 0
        lock = threading.Lock()

        def slow_mock(prompt, system_prompt):
            nonlocal max_seen
            with lock:
                active_calls.append(1)
                if len(active_calls) > max_seen:
                    max_seen = len(active_calls)
            time.sleep(0.05)
            with lock:
                active_calls.pop()
            return json.dumps({
                "product_name": "Spoon",
                "category": "Kitchen",
                "supplier_name": "BambooCo",
                "supplier_sku": "B100",
                "supplier_price": "10.00",
                "competitor_price": "30.00",
                "proposed_selling_price": "25.00",
                "estimated_shipping_cost": "5.00",
                "estimated_return_rate": 0.01,
                "target_customer": "All consumers",
                "key_features": ["Eco-friendly feature"],
                "verdict": "RECOMMENDED",
                "reasoning": "Valid reasoning with more than ten characters.",
            })

        client = OllamaClient(mock_handler=slow_mock)

        threads = [
            threading.Thread(target=lambda: client.generate("test", schema_model=ProductHunterOutput))
            for _ in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Concurrency must never exceed 1
        self.assertEqual(max_seen, 1)

    def test_schema_validation_rejection(self):
        """Invalid JSON or missing fields raises SchemaValidationError."""
        def bad_mock(prompt, system_prompt):
            return json.dumps({"incomplete": "data"})

        client = OllamaClient(mock_handler=bad_mock)
        with self.assertRaises(SchemaValidationError):
            client.generate("test", schema_model=ProductHunterOutput)


class TestAIAgents(unittest.TestCase):
    """Test Product Hunter and Listing Content agent business logic."""

    def test_product_hunter_positive_margin(self):
        def hunter_mock(prompt, system_prompt):
            return json.dumps({
                "product_name": "Stainless Steel Lunch Box",
                "category": "Kitchen",
                "supplier_name": "SteelCraft",
                "supplier_sku": "SC-LUNCH-01",
                "supplier_price": "300.00",
                "competitor_price": "799.00",
                "proposed_selling_price": "699.00",
                "estimated_shipping_cost": "60.00",
                "estimated_return_rate": 0.04,
                "target_customer": "Office commuters",
                "key_features": ["Leak proof", "Food grade 304"],
                "verdict": "RECOMMENDED",
                "reasoning": "Strong margin and healthy demand.",
            })

        client = OllamaClient(mock_handler=hunter_mock)
        agent = ProductHunterAgent(client=client)

        res = agent.run({
            "raw_text": "High grade lunch box from verified supplier",
            "supplier_name": "SteelCraft",
            "supplier_sku": "SC-LUNCH-01",
            "category": "Kitchen",
            "supplier_cost": 300.0,
        })

        self.assertEqual(res["agent_id"], "product_hunter")
        self.assertTrue(res["metrics"]["can_publish"])
        self.assertGreater(float(res["metrics"]["contribution_profit_inr"]), 200.0)
        self.assertEqual(res["approval_request"]["action_type"], "PublishProduct")

    def test_product_hunter_rejects_negative_margin(self):
        """When proposed price yields negative contribution profit, verdict is forced to REJECTED."""
        def loss_mock(prompt, system_prompt):
            return json.dumps({
                "product_name": "Loss Making Mug",
                "category": "Kitchen",
                "supplier_name": "MugCo",
                "supplier_sku": "MUG-01",
                "supplier_price": "500.00", # Cost 500
                "competitor_price": "400.00",
                "proposed_selling_price": "350.00", # Selling at 350 -> loss!
                "estimated_shipping_cost": "80.00",
                "estimated_return_rate": 0.10,
                "target_customer": "Coffee drinkers",
                "key_features": ["Ceramic"],
                "verdict": "RECOMMENDED", # LLM incorrectly recommends
                "reasoning": "A simple standard coffee mug for daily use.",
            })

        client = OllamaClient(mock_handler=loss_mock)
        agent = ProductHunterAgent(client=client)

        res = agent.run({
            "raw_text": "Ceramic coffee mug",
            "supplier_name": "MugCo",
            "supplier_sku": "MUG-01",
            "category": "Kitchen",
            "supplier_cost": 500.0,
        })

        # Deterministic logic overrides hallucinated verdict
        self.assertFalse(res["metrics"]["can_publish"])
        self.assertEqual(res["output"]["verdict"], "REJECTED")
        self.assertIn("Negative contribution profit", res["output"]["reasoning"])
        self.assertEqual(res["approval_request"]["risk_level"], "High")

    def test_listing_content_agent_strips_banned_superlatives(self):
        """Superlatives like 'world's best' fail schema validation."""
        def superlative_mock(prompt, system_prompt):
            return json.dumps({
                "title": "The World's Best Bamboo Cutlery Set", # Banned superlative!
                "short_description": "A completely revolutionary set of bamboo utensils for everyone.",
                "highlights": ["100% natural", "Lightweight"],
                "pros": ["Eco-friendly", "Smooth finish"],
                "cons": ["Hand wash only"],
                "seo_meta_title": "Bamboo Cutlery",
                "seo_meta_description": "Buy bamboo cutlery for sustainable daily dining.",
            })

        client = OllamaClient(mock_handler=superlative_mock)
        agent = ListingContentAgent(client=client)

        with self.assertRaises(SchemaValidationError) as ctx:
            agent.run({
                "product_name": "Bamboo Cutlery Set",
                "category": "Kitchen",
                "key_features": ["Natural bamboo", "Dishwasher safe"],
                "target_customer": "Eco shoppers",
            })
        self.assertIn("banned superlative", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
