"""ACOM Core — AI Task Service.

Coordinates creation, deduplication, schema-gated result persistence,
and lifecycle state machine for AI Tasks (DATA_DICTIONARY §8, API_CONTRACTS §5).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import frappe
from frappe.utils import add_to_date, now_datetime

from acom_core.ai_operations.doctype.ai_task.ai_task import compute_canonical_input_hash
from acom_core.ai_operations.services.schema_validator import validate_ai_output


def create_ai_task(
    task_type: str,
    agent_id: str,
    model: str,
    input_payload: Any,
    correlation_id: str | None = None,
    input_reference: str | None = None,
    ttl_hours: int = 24,
) -> dict[str, Any]:
    """Create or deduplicate an AI Task.

    Per DATA_DICTIONARY §8:
    input_hash + agent_id + task_type is the dedupe key; a duplicate within
    the TTL returns the existing task.
    """
    input_hash = compute_canonical_input_hash(input_payload)

    # Check for existing task within TTL
    cutoff = add_to_date(now_datetime(), hours=-ttl_hours)
    existing_tasks = frappe.get_all(
        "AI Task",
        filters={
            "input_hash": input_hash,
            "agent_id": agent_id,
            "task_type": task_type,
            "created_at": [">=", cutoff],
            "status": ["in", ["Queued", "Running", "Succeeded"]],
        },
        fields=["name", "task_id", "status", "created_at"],
        order_by="created_at desc",
        limit_page_length=1,
    )

    if existing_tasks:
        existing = existing_tasks[0]
        return {
            "ok": True,
            "task_id": existing["task_id"],
            "status": existing["status"],
            "duplicate": True,
        }

    # Create new task
    task_id = str(uuid.uuid4())
    task_doc = frappe.get_doc(
        {
            "doctype": "AI Task",
            "task_id": task_id,
            "task_type": task_type,
            "agent_id": agent_id,
            "model": model,
            "status": "Queued",
            "input_hash": input_hash,
            "input_reference": input_reference or "",
            "input_payload": json.dumps(input_payload) if isinstance(input_payload, (dict, list)) else str(input_payload or ""),
            "correlation_id": correlation_id or "",
            "retry_count": 0,
            "max_retries": 2,
        }
    )
    task_doc.insert(ignore_permissions=True)

    return {
        "ok": True,
        "task_id": task_doc.task_id,
        "status": "Queued",
        "duplicate": False,
    }


def record_ai_task_result(
    task_id: str,
    output: Any,
    schema_version: str = "1.0",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    output_reference: str | None = None,
) -> dict[str, Any]:
    """Process an AI result submission with strict schema verification.

    Per API_CONTRACTS §5:
    ai/result rejects an output that fails schema validation, with SCHEMA_INVALID
    and the failing pointer.
    """
    if not frappe.db.exists("AI Task", task_id):
        return {
            "ok": False,
            "error_code": "NOT_FOUND",
            "message": f"AI Task '{task_id}' not found",
        }

    task_doc = frappe.get_doc("AI Task", task_id)

    # Validate output against task schema
    is_valid, err_msg, cleaned_output = validate_ai_output(task_doc.task_type, output)

    if not is_valid:
        task_doc.mark_rejected(
            error_code="SCHEMA_INVALID",
            error_details=err_msg,
            output_payload=output,
        )
        return {
            "ok": False,
            "error_code": "SCHEMA_INVALID",
            "message": f"AI output failed schema validation: {err_msg}",
            "task_id": task_id,
            "status": "Rejected",
        }

    task_doc.mark_succeeded(
        output_payload=cleaned_output,
        output_reference=output_reference,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )

    return {
        "ok": True,
        "task_id": task_id,
        "status": "Succeeded",
        "data": cleaned_output,
    }
