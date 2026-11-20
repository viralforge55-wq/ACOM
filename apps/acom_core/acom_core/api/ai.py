"""ACOM Core — AI Operations Protected Internal API (API_CONTRACTS.md §5, §7).

Endpoints:
- POST /api/method/acom_core.api.ai.create_task
- POST /api/method/acom_core.api.ai.submit_result
- GET  /api/method/acom_core.api.ai.get_task_status
- POST /api/method/acom_core.api.ai.create_approval
- POST /api/method/acom_core.api.ai.decide_approval
- GET  /api/method/acom_core.api.ai.get_approval_request
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

from acom_core.ai_operations.services.approval_service import (
    create_approval_request,
    decide_approval_request,
)
from acom_core.ai_operations.services.task_service import (
    create_ai_task,
    record_ai_task_result,
)
from acom_core.api.errors import AcomApiError, error_response, ok_response

AI_RUNNER_ROLES = (
    "System Manager",
    "ACOM Manager",
    "ACOM Editor",
)

APPROVAL_ROLES = (
    "System Manager",
    "ACOM Manager",
    "ACOM Finance",
)


def _check_authenticated_role(allowed_roles: tuple[str, ...]) -> None:
    """Ensure session is not Guest and has one of the allowed roles."""
    user = frappe.session.user if frappe.session else "Guest"
    if not user or user == "Guest":
        raise AcomApiError("UNAUTHENTICATED", "Authentication required.", status_code=401)

    roles = set(frappe.get_roles(user))
    if not any(r in roles for r in allowed_roles):
        raise AcomApiError("FORBIDDEN", "Insufficient role privileges.", status_code=403)


@frappe.whitelist(methods=["POST"])
def create_task(
    task_type: str,
    agent_id: str,
    model: str,
    input_payload: Any = None,
    correlation_id: str | None = None,
    input_reference: str | None = None,
) -> dict[str, Any]:
    """Create or deduplicate an AI Task.

    Requires authenticated runner/manager role. Never accessible to Guest.
    """
    try:
        _check_authenticated_role(AI_RUNNER_ROLES)

        if isinstance(input_payload, str):
            try:
                input_payload = json.loads(input_payload)
            except Exception:
                pass

        res = create_ai_task(
            task_type=task_type,
            agent_id=agent_id,
            model=model,
            input_payload=input_payload,
            correlation_id=correlation_id,
            input_reference=input_reference,
        )
        return ok_response(res, status_code=201 if not res.get("duplicate") else 200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception as exc:
        return error_response("INTERNAL_ERROR", str(exc) or "Task creation failed", status_code=500)


@frappe.whitelist(methods=["POST"])
def submit_result(
    task_id: str,
    output: Any,
    schema_version: str = "1.0",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    output_reference: str | None = None,
) -> dict[str, Any]:
    """Submit validated or unvalidated model output for an AI Task.

    Implements POST /api/internal/ai/result per API_CONTRACTS §5.
    Returns 422 SCHEMA_INVALID if output fails declared schema validation.
    """
    try:
        _check_authenticated_role(AI_RUNNER_ROLES)

        if isinstance(output, str):
            try:
                output = json.loads(output)
            except Exception:
                pass

        res = record_ai_task_result(
            task_id=task_id,
            output=output,
            schema_version=schema_version,
            prompt_tokens=int(prompt_tokens or 0),
            completion_tokens=int(completion_tokens or 0),
            output_reference=output_reference,
        )

        if not res.get("ok"):
            code = res.get("error_code", "SCHEMA_INVALID")
            status = 404 if code == "NOT_FOUND" else 422
            return error_response(code, res.get("message", "Schema validation failed"), status_code=status, details=res)

        return ok_response(res, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception as exc:
        return error_response("INTERNAL_ERROR", str(exc) or "Result submission failed", status_code=500)


@frappe.whitelist(methods=["GET"])
def get_task_status(task_id: str) -> dict[str, Any]:
    """Retrieve status and metadata for an AI Task."""
    try:
        _check_authenticated_role(AI_RUNNER_ROLES)

        if not frappe.db.exists("AI Task", task_id):
            return error_response("NOT_FOUND", f"AI Task '{task_id}' not found", status_code=404)

        task = frappe.get_doc("AI Task", task_id)
        data = {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "agent_id": task.agent_id,
            "model": task.model,
            "status": task.status,
            "retry_count": task.retry_count,
            "max_retries": task.max_retries,
            "created_at": str(task.created_at),
            "started_at": str(task.started_at) if task.started_at else None,
            "completed_at": str(task.completed_at) if task.completed_at else None,
            "duration_ms": task.duration_ms,
            "output_validated": task.output_validated,
            "error_code": task.error_code,
            "error_details": task.error_details,
            "prompt_tokens": task.prompt_tokens,
            "completion_tokens": task.completion_tokens,
        }
        return ok_response(data)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception as exc:
        return error_response("INTERNAL_ERROR", str(exc) or "Failed to get task", status_code=500)


@frappe.whitelist(methods=["POST"])
def create_approval(
    action_type: str,
    related_doctype: str,
    related_name: str,
    recommendation: str,
    rationale: str | None = None,
    estimated_financial_impact: float = 0.0,
    ai_task: str | None = None,
    risk_level: str = "Medium",
) -> dict[str, Any]:
    """Create an AI Approval Request."""
    try:
        _check_authenticated_role(AI_RUNNER_ROLES)

        res = create_approval_request(
            action_type=action_type,
            related_doctype=related_doctype,
            related_name=related_name,
            recommendation=recommendation,
            rationale=rationale,
            estimated_financial_impact=float(estimated_financial_impact or 0.0),
            ai_task=ai_task,
            risk_level=risk_level,
        )
        return ok_response(res, status_code=201)
    except AcomApiError as exc:
        return exc.to_response()
    except frappe.ValidationError as exc:
        msg = str(exc) or (frappe.local.message_log and json.loads(frappe.local.message_log[-1]).get("message")) or "Validation failed"
        return error_response("VALIDATION_ERROR", msg, status_code=400)
    except Exception as exc:
        return error_response("VALIDATION_ERROR", str(exc) or "Failed to create approval request", status_code=400)


@frappe.whitelist(methods=["POST"])
def decide_approval(
    request_id: str,
    decision: str,
    decision_note: str | None = None,
) -> dict[str, Any]:
    """Human decision (Approved or Rejected) on an AI Approval Request.

    Enforces A5 financial firewall: Purchase Orders and Refunds require
    System Manager or ACOM Finance roles strictly.
    """
    try:
        _check_authenticated_role(APPROVAL_ROLES)

        res = decide_approval_request(
            request_id=request_id,
            decision=decision,
            decision_note=decision_note,
            user=frappe.session.user,
        )
        if not res.get("ok"):
            code = res.get("error_code", "VALIDATION_ERROR")
            status = 404 if code == "NOT_FOUND" else 400
            return error_response(code, res.get("message", "Decision failed"), status_code=status)
        return ok_response(res, status_code=200)
    except AcomApiError as exc:
        return exc.to_response()
    except frappe.PermissionError as exc:
        msg = str(exc) or (frappe.local.message_log and json.loads(frappe.local.message_log[-1]).get("message")) or "Insufficient permissions"
        return error_response("FORBIDDEN", msg, status_code=403)
    except frappe.ValidationError as exc:
        msg = str(exc) or (frappe.local.message_log and json.loads(frappe.local.message_log[-1]).get("message")) or "Validation error"
        return error_response("VALIDATION_ERROR", msg, status_code=400)
    except Exception as exc:
        return error_response("INTERNAL_ERROR", str(exc) or "Unexpected error", status_code=500)


@frappe.whitelist(methods=["GET"])
def get_approval_request(request_id: str) -> dict[str, Any]:
    """Retrieve details of an AI Approval Request."""
    try:
        _check_authenticated_role(APPROVAL_ROLES)

        if not frappe.db.exists("AI Approval Request", request_id):
            return error_response("NOT_FOUND", f"Approval Request '{request_id}' not found", status_code=404)

        req = frappe.get_doc("AI Approval Request", request_id)
        data = {
            "request_id": req.request_id,
            "action_type": req.action_type,
            "approval_status": req.approval_status,
            "risk_level": req.risk_level,
            "related_doctype": req.related_doctype,
            "related_name": req.related_name,
            "ai_task": req.ai_task,
            "recommendation": req.recommendation,
            "rationale": req.rationale,
            "estimated_financial_impact": req.estimated_financial_impact,
            "approved_by": req.approved_by,
            "approval_timestamp": str(req.approval_timestamp) if req.approval_timestamp else None,
            "decision_note": req.decision_note,
            "expires_at": str(req.expires_at) if req.expires_at else None,
        }
        return ok_response(data)
    except AcomApiError as exc:
        return exc.to_response()
    except Exception as exc:
        return error_response("INTERNAL_ERROR", str(exc) or "Failed to get approval request", status_code=500)
