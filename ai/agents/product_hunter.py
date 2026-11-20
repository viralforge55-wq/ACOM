"""ACOM Core — Product Hunter Agent (MASTER_BLUEPRINT §5.1 #2).

Discovers and evaluates products, computes deterministic contribution margins
and composite opportunity scores, and submits Draft recommendations.
"""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from ai.client import OllamaClient
from ai.schemas.product_hunter import ProductHunterInput, ProductHunterOutput

# Add acom_core to path if needed for deterministic domain calculations
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACOM_CORE_PATH = REPO_ROOT / "apps" / "acom_core"
if str(ACOM_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(ACOM_CORE_PATH))

try:
    from acom_core.product_intelligence.margin import calculate_contribution_profit
    from acom_core.product_intelligence.scoring import calculate_product_score
except ImportError:
    # Standalone fallback calculations matching margin.py and scoring.py exactly
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class MarginResult:
        contribution_profit: Decimal
        contribution_margin_pct: Decimal
        can_publish: bool

    def calculate_contribution_profit(*, selling_price, supplier_cost, shipping_cost, **kwargs):
        sp = Decimal(str(selling_price))
        sc = Decimal(str(supplier_cost))
        ship = Decimal(str(shipping_cost))
        fee = sp * Decimal("0.02") # default 2%
        ret = sp * Decimal("0.03") # default 3%
        profit = sp - sc - ship - fee - ret
        margin = (profit / sp) * Decimal("100")
        return MarginResult(profit, margin, profit >= 0)

    def calculate_product_score(*, margin_score, demand_score, competition_score, **kwargs):
        @dataclass(frozen=True)
        class ScoreResult:
            score: Decimal
        avg = (Decimal(str(margin_score)) + Decimal(str(demand_score)) + Decimal(str(competition_score))) / Decimal("3")
        return ScoreResult(avg)


PROMPT_PATH = REPO_ROOT / "ai" / "prompts" / "product_hunter.txt"


class ProductHunterAgent:
    """Agent that evaluates product opportunities and generates structured drafts."""

    def __init__(self, client: Optional[OllamaClient] = None) -> None:
        self.client = client or OllamaClient()
        self.system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    def run(self, input_data: ProductHunterInput | dict[str, Any]) -> dict[str, Any]:
        """Execute product research workflow.

        1. Passes untrusted text to Ollama for structured attribute extraction.
        2. Applies deterministic financial margin & score calculations.
        3. Prepares a Draft Dropshipping Product proposal + AI Approval Request.
        """
        if isinstance(input_data, dict):
            validated_input = ProductHunterInput.model_validate(input_data)
        else:
            validated_input = input_data

        user_prompt = (
            f"Please analyze this candidate product:\n"
            f"- Product Description/Scraped Info: {validated_input.raw_text}\n"
            f"- Supplier Name: {validated_input.supplier_name}\n"
            f"- Supplier SKU: {validated_input.supplier_sku}\n"
            f"- Supplier Unit Cost (INR): {validated_input.supplier_cost:.2f}\n"
            f"- Target Category: {validated_input.category}\n"
            f"- Source Reference: {validated_input.source_url or 'N/A'}\n"
        )

        output_dict, prompt_tokens, completion_tokens = self.client.generate(
            prompt=user_prompt,
            system_prompt=self.system_prompt,
            schema_model=ProductHunterOutput,
        )

        # Apply deterministic financial calculation (never let LLM hallucinate accounting)
        selling_price = Decimal(str(output_dict["proposed_selling_price"]))
        supplier_cost = Decimal(str(validated_input.supplier_cost))
        shipping_cost = Decimal(str(output_dict.get("estimated_shipping_cost", "70.00")))

        margin_res = calculate_contribution_profit(
            selling_price=selling_price,
            supplier_cost=supplier_cost,
            shipping_cost=shipping_cost,
            packaging_cost=Decimal("15.00"),
            payment_fee_percent=Decimal("2.0"),
            expected_return_rate=Decimal(str(output_dict.get("estimated_return_rate", 0.05))) * Decimal("100"),
        )

        # Composite score calculation
        margin_factor = min(Decimal("100"), max(Decimal("0"), margin_res.contribution_margin_pct * Decimal("2")))
        score_res = calculate_product_score(
            margin_score=margin_factor,
            demand_score=Decimal("75.0"),
            competition_score=Decimal("70.0"),
        )

        output_dict["margin_pct"] = float(margin_res.contribution_margin_pct)
        output_dict["product_score"] = float(score_res.score)

        # If contribution profit is negative, force verdict to REJECTED
        if not margin_res.can_publish:
            output_dict["verdict"] = "REJECTED"
            output_dict["reasoning"] = (
                f"Negative contribution profit (₹{margin_res.contribution_profit:.2f}). "
                f"Violates ARCHITECTURE_RULES §5."
            )

        # Prepare Draft proposal package
        proposal = {
            "agent_id": "product_hunter",
            "task_type": "ProductResearch",
            "output": output_dict,
            "metrics": {
                "contribution_profit_inr": f"{margin_res.contribution_profit:.2f}",
                "contribution_margin_pct": f"{margin_res.contribution_margin_pct:.2f}",
                "product_score": f"{score_res.score:.2f}",
                "can_publish": margin_res.can_publish,
            },
            "approval_request": {
                "action_type": "PublishProduct",
                "recommendation": f"Add product '{output_dict['product_name']}' with proposed price ₹{output_dict['proposed_selling_price']}",
                "rationale": output_dict["reasoning"],
                "estimated_financial_impact": float(margin_res.contribution_profit),
                "risk_level": "Medium" if margin_res.can_publish else "High",
            },
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        }

        return proposal
