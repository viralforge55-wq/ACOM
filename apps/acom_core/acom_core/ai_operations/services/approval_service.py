"""ACOM Core — AI Approval Service.

Orchestrates approval request lifecycle, execution after human approval,
and role-restricted state transitions (DATA_DICTIONARY §9, SECURITY_POLICY §7).
"""

from __future__ import annotations

import uuid
from typing import Any

import frappe
from frappe.utils import now_datetime


def create_approval_request(
    action_type: str,
    related_doctype: str,
    related_name: str,
    recommendation: str,
    rationale: str | None = None,
    estimated_financial_impact: float = 0.0,
    ai_task: str | None = None,
    risk_level: str = "Medium",
) -> dict[str, Any]:
    """Create a new pending AI Approval Request."""
    request_id = str(uuid.uuid4())
    doc = frappe.get_doc(
        {
            "doctype": "AI Approval Request",
            "request_id": request_id,
            "action_type": action_type,
            "related_doctype": related_doctype,
            "related_name": related_name,
            "recommendation": recommendation,
            "rationale": rationale or "",
            "estimated_financial_impact": estimated_financial_impact,
            "ai_task": ai_task,
            "risk_level": risk_level,
            "approval_status": "Pending",
        }
    )
    doc.insert(ignore_permissions=True)

    return {
        "ok": True,
        "request_id": doc.request_id,
        "approval_status": doc.approval_status,
        "risk_level": doc.risk_level,
    }


def decide_approval_request(
    request_id: str,
    decision: str,
    decision_note: str | None = None,
    user: str | None = None,
) -> dict[str, Any]:
    """Decide an AI Approval Request (Approved or Rejected).

    Applies role permissions and triggers downstream document actions upon approval.
    """
    if not frappe.db.exists("AI Approval Request", request_id):
        return {
            "ok": False,
            "error_code": "NOT_FOUND",
            "message": f"AI Approval Request '{request_id}' not found",
        }

    doc = frappe.get_doc("AI Approval Request", request_id)

    if decision == "Approved":
        doc.approve(user=user)

        # Downstream execution upon human approval
        if doc.action_type == "PublishProduct":
            if doc.related_doctype == "Dropshipping Product":
                prod = frappe.get_doc("Dropshipping Product", doc.related_name)
                prod.status = "Published"
                prod.save()
            elif doc.related_doctype == "Affiliate Product":
                prod = frappe.get_doc("Affiliate Product", doc.related_name)
                prod.status = "Published"
                prod.save()

    elif decision == "Rejected":
        if not decision_note:
            return {
                "ok": False,
                "error_code": "VALIDATION_ERROR",
                "message": "decision_note is mandatory when rejecting an AI Approval Request",
            }
        doc.reject(decision_note=decision_note, user=user)
    else:
        return {
            "ok": False,
            "error_code": "VALIDATION_ERROR",
            "message": f"Invalid decision '{decision}'. Must be 'Approved' or 'Rejected'",
        }

    return {
        "ok": True,
        "request_id": doc.request_id,
        "approval_status": doc.approval_status,
        "approved_by": doc.approved_by,
        "approval_timestamp": str(doc.approval_timestamp),
    }


def expire_stale_approval_requests() -> int:
    """Mark expired approval requests as Expired (per DATA_DICTIONARY §9)."""
    now = now_datetime()
    expired_requests = frappe.get_all(
        "AI Approval Request",
        filters={
            "approval_status": "Pending",
            "expires_at": ["<", now],
        },
        fields=["name", "request_id"],
    )

    count = 0
    for req in expired_requests:
        doc = frappe.get_doc("AI Approval Request", req["name"])
        doc.approval_status = "Expired"
        doc.save()
        count += 1

    return count
