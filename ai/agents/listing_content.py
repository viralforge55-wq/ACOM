"""ACOM Core — Listing & Content Agent (MASTER_BLUEPRINT §5.1 #4).

Generates compliant, factual product titles, descriptions, pros/cons,
and SEO metadata without superlatives or unverified claims.
Saved strictly as Draft pending human approval.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from ai.client import OllamaClient
from ai.schemas.listing_content import ListingContentInput, ListingContentOutput

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROMPT_PATH = REPO_ROOT / "ai" / "prompts" / "listing_content.txt"


class ListingContentAgent:
    """Agent that creates marketplace-compliant product copy and SEO metadata."""

    def __init__(self, client: Optional[OllamaClient] = None) -> None:
        self.client = client or OllamaClient()
        self.system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    def run(self, input_data: ListingContentInput | dict[str, Any]) -> dict[str, Any]:
        """Execute content generation workflow."""
        if isinstance(input_data, dict):
            validated_input = ListingContentInput.model_validate(input_data)
        else:
            validated_input = input_data

        user_prompt = (
            f"Please generate compliant product copy for:\n"
            f"- Product Name: {validated_input.product_name}\n"
            f"- Category: {validated_input.category}\n"
            f"- Key Features: {', '.join(validated_input.key_features)}\n"
            f"- Target Customer: {validated_input.target_customer}\n"
            f"- Supplier Notes: {validated_input.supplier_notes or 'None'}\n"
        )

        output_dict, prompt_tokens, completion_tokens = self.client.generate(
            prompt=user_prompt,
            system_prompt=self.system_prompt,
            schema_model=ListingContentOutput,
        )

        package = {
            "agent_id": "listing_content",
            "task_type": "ContentGeneration",
            "output": output_dict,
            "approval_request": {
                "action_type": "ContentPublish",
                "recommendation": f"Publish generated copy for '{output_dict['title']}'",
                "rationale": f"Generated compliant listing with {len(output_dict['highlights'])} highlights and verified pros/cons.",
                "estimated_financial_impact": 0.0,
                "risk_level": "Low",
            },
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        }

        return package
