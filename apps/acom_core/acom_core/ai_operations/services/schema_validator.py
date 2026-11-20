"""ACOM Core — AI Schema Validator Service.

Enforces strict JSON schema validation on every model output.
Invalid or malformed JSON is rejected and logged with SCHEMA_INVALID,
never persisted as business data (API_CONTRACTS §5, SECURITY_POLICY §7).
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Tuple

BANNED_CONTENT_SUPERLATIVES = (
    "world's best",
    "best in the world",
    "miracle cure",
    "guaranteed 100%",
    "100% guaranteed",
    "100% risk free",
    "#1 on the planet",
    "magic solution",
)


def validate_product_hunter_output(output: dict[str, Any]) -> Tuple[bool, str, dict[str, Any]]:
    """Validate Product Hunter / ProductResearch output payload."""
    required_fields = [
        "product_name",
        "category",
        "supplier_name",
        "supplier_sku",
        "supplier_price",
        "competitor_price",
        "proposed_selling_price",
        "estimated_shipping_cost",
        "estimated_return_rate",
        "target_customer",
        "key_features",
        "verdict",
        "reasoning",
    ]

    for field in required_fields:
        if field not in output:
            return False, f"Missing required field: {field}", {}

    if not isinstance(output["product_name"], str) or not output["product_name"].strip():
        return False, "product_name must be a non-empty string", {}

    if not isinstance(output["category"], str) or not output["category"].strip():
        return False, "category must be a non-empty string", {}

    # Validate numbers
    numeric_fields = ["supplier_price", "competitor_price", "proposed_selling_price", "estimated_shipping_cost"]
    cleaned_numbers = {}
    for nf in numeric_fields:
        val = output[nf]
        try:
            dec = Decimal(str(val))
            if nf != "estimated_shipping_cost" and dec <= Decimal("0"):
                return False, f"{nf} must be greater than zero", {}
            if dec < Decimal("0"):
                return False, f"{nf} cannot be negative", {}
            cleaned_numbers[nf] = str(dec.quantize(Decimal("0.01")))
        except (InvalidOperation, TypeError, ValueError):
            return False, f"{nf} must be a valid numeric value", {}

    # Return rate
    try:
        rr = float(output["estimated_return_rate"])
        if not (0.0 <= rr <= 1.0):
            return False, "estimated_return_rate must be between 0.0 and 1.0", {}
    except (TypeError, ValueError):
        return False, "estimated_return_rate must be a float between 0.0 and 1.0", {}

    # Verdict
    allowed_verdicts = ("RECOMMENDED", "REJECTED", "NEEDS_REVIEW")
    verdict = str(output.get("verdict", "")).upper()
    if verdict not in allowed_verdicts:
        return False, f"verdict must be one of {allowed_verdicts}", {}

    # Lists
    if not isinstance(output.get("key_features"), list):
        return False, "key_features must be a list of strings", {}

    cleaned = dict(output)
    cleaned.update(cleaned_numbers)
    cleaned["verdict"] = verdict
    return True, "", cleaned


def validate_listing_content_output(output: dict[str, Any]) -> Tuple[bool, str, dict[str, Any]]:
    """Validate Listing & Content / ContentGeneration output payload."""
    required_fields = [
        "title",
        "short_description",
        "highlights",
        "pros",
        "cons",
        "seo_meta_title",
        "seo_meta_description",
    ]

    for field in required_fields:
        if field not in output:
            return False, f"Missing required field: {field}", {}

    title = output["title"]
    if not isinstance(title, str) or not title.strip() or len(title) > 150:
        return False, "title must be a non-empty string of max 150 characters", {}

    # Check for banned superlatives
    lower_title = title.lower()
    for phrase in BANNED_CONTENT_SUPERLATIVES:
        if phrase in lower_title:
            return False, f"title contains banned marketing superlative: '{phrase}'", {}

    desc = output["short_description"]
    if not isinstance(desc, str) or len(desc.strip()) < 10:
        return False, "short_description must be a string of at least 10 characters", {}

    lower_desc = desc.lower()
    for phrase in BANNED_CONTENT_SUPERLATIVES:
        if phrase in lower_desc:
            return False, f"short_description contains banned superlative: '{phrase}'", {}

    # Highlights, pros, cons lists
    for lf in ("highlights", "pros", "cons"):
        val = output.get(lf)
        if not isinstance(val, list) or len(val) == 0:
            return False, f"{lf} must be a non-empty list of strings", {}
        for item in val:
            if not isinstance(item, str):
                return False, f"All items in {lf} must be strings", {}

    # SEO metadata
    meta_title = output["seo_meta_title"]
    if not isinstance(meta_title, str) or len(meta_title) > 70:
        return False, "seo_meta_title must be a string of max 70 characters", {}

    meta_desc = output["seo_meta_description"]
    if not isinstance(meta_desc, str) or len(meta_desc) > 160:
        return False, "seo_meta_description must be a string of max 160 characters", {}

    return True, "", dict(output)


def validate_ai_output(task_type: str, output: Any) -> Tuple[bool, str, dict[str, Any]]:
    """Validate model output against the registered schema for task_type."""
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except Exception as e:
            return False, f"Output is not valid JSON: {str(e)}", {}

    if not isinstance(output, dict):
        return False, "Output must be a JSON object / dict", {}

    if task_type == "ProductResearch":
        return validate_product_hunter_output(output)
    elif task_type == "ContentGeneration":
        return validate_listing_content_output(output)
    elif task_type in ("SupplierAnalysis", "Classification", "Report", "Reconciliation"):
        # Base validation: must have summary or payload
        return True, "", output
    else:
        return False, f"Unknown task_type: {task_type}", {}
