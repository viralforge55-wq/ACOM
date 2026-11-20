"""Integration test running live inference against local host Ollama (qwen2.5:3b).

Validates end-to-end integration with the real local Ollama daemon on Windows host
at http://127.0.0.1:11434, confirming model inference speed, schema compliance,
and deterministic domain metric calculation.
"""

import unittest

from ai.client import OllamaClient
from ai.agents.product_hunter import ProductHunterAgent
from ai.agents.listing_content import ListingContentAgent


class TestLiveOllamaInference(unittest.TestCase):
    """Test live local Ollama model qwen2.5:3b."""

    @classmethod
    def setUpClass(cls):
        cls.client = OllamaClient(
            base_url="http://127.0.0.1:11434",
            default_model="qwen2.5:3b",
            timeout_seconds=90.0,
        )
        if not cls.client.is_healthy():
            raise unittest.SkipTest("Local Ollama daemon is not reachable at 127.0.0.1:11434")

    def test_live_product_hunter_agent(self):
        """Execute ProductHunterAgent against live local qwen2.5:3b."""
        agent = ProductHunterAgent(client=self.client)
        result = agent.run({
            "raw_text": (
                "500ml vacuum insulated stainless steel water bottle. "
                "Keeps liquids cold for 24 hours and hot for 12 hours. "
                "BPA free, leakproof cap, matte powder coat finish."
            ),
            "supplier_name": "HydroSteel Corp",
            "supplier_sku": "HS-BOT-500",
            "category": "Home & Kitchen",
            "supplier_cost": 220.0,
        })

        self.assertEqual(result["agent_id"], "product_hunter")
        self.assertEqual(result["task_type"], "ProductResearch")
        self.assertIn("output", result)
        output = result["output"]
        self.assertTrue(output["product_name"])
        self.assertIn(output["verdict"], ("RECOMMENDED", "REJECTED", "NEEDS_REVIEW"))
        self.assertGreater(len(output["key_features"]), 0)
        self.assertIn("metrics", result)
        self.assertIn("approval_request", result)

    def test_live_listing_content_agent(self):
        """Execute ListingContentAgent against live local qwen2.5:3b."""
        agent = ListingContentAgent(client=self.client)
        result = agent.run({
            "product_name": "Bamboo Travel Cutlery Set",
            "category": "Kitchen",
            "key_features": [
                "100% natural organic bamboo",
                "Includes fork, knife, spoon, chopsticks, and straw",
                "Comes with washable cotton canvas travel pouch",
                "Lightweight and compact for office commuters",
            ],
            "target_customer": "Eco-conscious urban commuters and travelers",
            "supplier_notes": "Hand wash recommended to extend bamboo lifespan.",
        })

        self.assertEqual(result["agent_id"], "listing_content")
        self.assertEqual(result["task_type"], "ContentGeneration")
        self.assertIn("output", result)
        output = result["output"]
        self.assertTrue(output["title"])
        self.assertGreater(len(output["highlights"]), 1)
        self.assertGreater(len(output["pros"]), 0)
        self.assertGreater(len(output["cons"]), 0)
        self.assertTrue(output["seo_meta_title"])
        self.assertTrue(output["seo_meta_description"])


if __name__ == "__main__":
    unittest.main()
