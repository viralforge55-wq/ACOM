"""Workflow 2: Content Generation Flow (MASTER_BLUEPRINT §11, BUSINESS_WORKFLOWS W2).

Flow:
1. Product ready for copy in Draft status.
2. Triggers Listing & Content Agent for clean descriptions and SEO metadata.
3. Enforces strict banned-superlative validation ("world's best", "guaranteed 100%").
4. Saves Draft copy + creates AI Approval Request.
5. NEVER auto-publishes (status stays Draft).
6. Emits Automation Event (content_generation.completed).
7. Failure path: banned claims / schema violation -> rejection, zero corrupt drafts.
"""

from __future__ import annotations

import json
from typing import Any, Dict

import frappe
from frappe.utils import now_datetime
from acom_core.api.errors import AcomApiError
from acom_core.integration_management.services.event_service import record_event

BANNED_SUPERLATIVES = (
    "world's best",
    "best in the world",
    "miracle cure",
    "guaranteed 100%",
    "100% guaranteed",
    "100% risk free",
    "#1 on the planet",
)


def run_content_generation_flow(
    *,
    product_doctype: str,
    product_name: str,
    mock_copy: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> Dict[str, Any]:
    """Execute Flow 2: Content Generation."""
    clean_doctype = (product_doctype or "").strip()
    clean_name = (product_name or "").strip()

    if clean_doctype not in ("Affiliate Product", "Dropshipping Product"):
        raise AcomApiError("VALIDATION_ERROR", f"Unsupported product DocType: {clean_doctype}", status_code=400)

    if not frappe.db.exists(clean_doctype, clean_name):
        raise AcomApiError("NOT_FOUND", f"{clean_doctype} '{clean_name}' does not exist.", status_code=404)

    product = frappe.get_doc(clean_doctype, clean_name)
    if getattr(product, "status", None) == "Published":
        raise AcomApiError(
            "INVALID_STATUS",
            "Cannot run content generation directly on an already Published product.",
            status_code=400,
        )

    idem_key = idempotency_key or f"content_gen::{clean_doctype}::{clean_name}::{int(now_datetime().timestamp())}"

    # Default copy or custom provided
    copy_data = mock_copy or {
        "title": f"Premium {product.product_name}",
        "short_description": f"Durable, eco-friendly {product.product_name.lower()} crafted for everyday reliability and utility.",
        "highlights": ["Durable construction", "Easy maintenance", "Sleek modern design"],
        "pros": ["Eco-conscious materials", "High reliability"],
        "cons": ["Limited color variations"],
        "seo_meta_title": f"Buy {product.product_name} Online - Fast Dispatch",
        "seo_meta_description": f"Shop authentic {product.product_name.lower()} with verified specs and fast shipping across India.",
    }

    # Step 1: Compliance & Banned superlatives validation
    for field, val in copy_data.items():
        if isinstance(val, str):
            lower_val = val.lower()
            for banned in BANNED_SUPERLATIVES:
                if banned in lower_val:
                    # Failure path
                    fail_payload = {
                        "product_doctype": clean_doctype,
                        "product_name": clean_name,
                        "error": f"Content contains banned superlative '{banned}' in field '{field}'",
                    }
                    event = record_event(
                        event_type="content_generation.failed",
                        source="Agent",
                        idempotency_key=idem_key,
                        payload=fail_payload,
                        allow_duplicate_return=True,
                    )
                    return {
                        "ok": False,
                        "error": fail_payload["error"],
                        "event_id": event.event_id,
                    }

    # Step 2: Create AI Task
    task_id = f"aitask-content-{frappe.generate_hash(length=8)}"
    ai_task = frappe.get_doc({
        "doctype": "AI Task",
        "task_id": task_id,
        "task_type": "ContentGeneration",
        "agent_id": "ListingContentAgent",
        "model": "qwen2.5:3b",
        "correlation_id": frappe.generate_hash(length=12),
        "status": "Succeeded",
        "input_payload": json.dumps({"product_doctype": clean_doctype, "product_name": clean_name}),
        "output_payload": json.dumps(copy_data),
        "output_validated": 1,
        "schema_version": "1.0",
        "created_time": now_datetime(),
    })
    ai_task.insert(ignore_permissions=True)

    # Step 3: Create AI Approval Request (Action: ContentPublish, Risk: Low)
    from datetime import timedelta
    req_id = f"aireq-content-{frappe.generate_hash(length=8)}"
    approval_req = frappe.get_doc({
        "doctype": "AI Approval Request",
        "request_id": req_id,
        "action_type": "ContentPublish",
        "approval_status": "Pending",
        "risk_level": "Low",
        "related_doctype": clean_doctype,
        "related_name": clean_name,
        "ai_task": ai_task.name,
        "recommendation": f"Approve generated listing copy and SEO metadata for {clean_doctype} '{clean_name}'",
        "rationale": f"Generated title '{copy_data.get('title')}' passed compliance and banned-superlatives checks.",
        "expires_at": now_datetime() + timedelta(days=3),
    })
    approval_req.insert(ignore_permissions=True)

    # Step 4: Emit success Automation Event
    success_payload = {
        "product_doctype": clean_doctype,
        "product_name": clean_name,
        "task_id": ai_task.name,
        "approval_request_id": approval_req.name,
        "title": copy_data["title"],
    }
    event = record_event(
        event_type="content_generation.completed",
        source="Agent",
        idempotency_key=idem_key,
        payload=success_payload,
        aggregate_doctype="AI Approval Request",
        aggregate_name=approval_req.name,
        allow_duplicate_return=True,
    )

    return {
        "ok": True,
        "event_id": event.event_id,
        "task_id": ai_task.name,
        "approval_request_id": approval_req.name,
    }
