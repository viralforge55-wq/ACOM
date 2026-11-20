"""Automation & Integration API endpoints (API_CONTRACTS.md §5, MASTER_BLUEPRINT §11).

Internal endpoints protected with HMAC-SHA256 signature verification:
- POST /api/method/acom_core.api.automation.inject_event
- POST /api/method/acom_core.api.automation.trigger_workflow
- GET  /api/method/acom_core.api.automation.get_event_status
"""

from __future__ import annotations

import json
from typing import Any, Dict

import frappe
from acom_core.api.errors import AcomApiError, error_response, ok_response
from acom_core.integration_management.security import require_m2m_hmac
from acom_core.integration_management.services.event_service import record_event
from acom_core.integration_management.workflows.content_generation import run_content_generation_flow
from acom_core.integration_management.workflows.order_monitor import run_order_monitor_flow
from acom_core.integration_management.workflows.product_research import run_product_research_flow
from acom_core.integration_management.workflows.reconciliation_monitor import run_reconciliation_monitor_flow
from acom_core.integration_management.workflows.supplier_monitor import run_supplier_monitor_flow


def _parse_request_payload() -> Dict[str, Any]:
    """Safely parse JSON request body or form dict."""
    req = getattr(frappe.local, "request", None)
    if req:
        raw = req.get_data(cache=True)
        if raw:
            try:
                return json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                pass
    return dict(getattr(frappe.local, "form_dict", {}) or {})


@frappe.whitelist(allow_guest=True, methods=["POST"])
@require_m2m_hmac
def inject_event() -> Dict[str, Any]:
    """Inject an event into the outbox with DB-enforced idempotency key."""
    try:
        body = _parse_request_payload()
        event_type = body.get("event_type")
        idempotency_key = body.get("idempotency_key")
        payload = body.get("payload") or {}
        source = body.get("source") or "Agent"
        aggregate_doctype = body.get("aggregate_doctype")
        aggregate_name = body.get("aggregate_name")

        if not event_type or not idempotency_key:
            return error_response(
                "VALIDATION_ERROR",
                "event_type and idempotency_key are required.",
                status_code=400,
            )

        event = record_event(
            event_type=event_type,
            source=source,
            idempotency_key=idempotency_key,
            payload=payload,
            aggregate_doctype=aggregate_doctype,
            aggregate_name=aggregate_name,
        )

        return ok_response(
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "processing_status": event.processing_status,
                "idempotency_key": event.idempotency_key,
            },
            status_code=201,
        )

    except AcomApiError as exc:
        return exc.to_response()
    except Exception as exc:
        frappe.log_error("inject_event error", str(exc))
        return error_response("INTERNAL_ERROR", "Failed to inject automation event.", status_code=500)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@require_m2m_hmac
def trigger_workflow() -> Dict[str, Any]:
    """Trigger one of the 5 core automation workflows directly."""
    try:
        body = _parse_request_payload()
        workflow = body.get("workflow") or body.get("workflow_name")
        params = body.get("parameters") or body.get("params") or {}

        if not workflow:
            return error_response("VALIDATION_ERROR", "workflow is required.", status_code=400)

        if workflow == "product_research":
            res = run_product_research_flow(
                keyword=params.get("keyword"),
                category=params.get("category"),
                supplier_cost=float(params.get("supplier_cost", 0)),
                estimated_retail_price=float(params.get("estimated_retail_price", 0)),
                min_target_margin_pct=float(params.get("min_target_margin_pct", 15.0)),
                idempotency_key=params.get("idempotency_key"),
            )
            return ok_response(res)

        elif workflow == "content_generation":
            res = run_content_generation_flow(
                product_doctype=params.get("product_doctype"),
                product_name=params.get("product_name"),
                mock_copy=params.get("mock_copy"),
                idempotency_key=params.get("idempotency_key"),
            )
            return ok_response(res)

        elif workflow == "supplier_monitor":
            res = run_supplier_monitor_flow(
                feed_items=params.get("feed_items", []),
                idempotency_key=params.get("idempotency_key"),
            )
            return ok_response(res)

        elif workflow == "order_monitor":
            res = run_order_monitor_flow(
                stuck_checkout_minutes=int(params.get("stuck_checkout_minutes", 30)),
                stale_po_hours=int(params.get("stale_po_hours", 24)),
                idempotency_key=params.get("idempotency_key"),
            )
            return ok_response(res)

        elif workflow == "reconciliation_monitor":
            res = run_reconciliation_monitor_flow(
                overdue_pending_days=int(params.get("overdue_pending_days", 60)),
                idempotency_key=params.get("idempotency_key"),
            )
            return ok_response(res)

        else:
            return error_response(
                "UNKNOWN_WORKFLOW",
                f"Workflow '{workflow}' is not recognized. Options: product_research, content_generation, supplier_monitor, order_monitor, reconciliation_monitor.",
                status_code=400,
            )

    except AcomApiError as exc:
        return exc.to_response()
    except Exception as exc:
        frappe.log_error("trigger_workflow error", str(exc))
        return error_response("INTERNAL_ERROR", f"Failed to execute workflow: {str(exc)}", status_code=500)


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
@require_m2m_hmac
def get_event_status() -> Dict[str, Any]:
    """Fetch status and metadata for an Automation Event."""
    try:
        body = _parse_request_payload()
        event_id = body.get("event_id") or frappe.local.form_dict.get("event_id")
        idempotency_key = body.get("idempotency_key") or frappe.local.form_dict.get("idempotency_key")

        if not event_id and not idempotency_key:
            return error_response("VALIDATION_ERROR", "event_id or idempotency_key is required.", status_code=400)

        filters: Dict[str, Any] = {}
        if event_id:
            filters["event_id"] = event_id
        if idempotency_key:
            filters["idempotency_key"] = idempotency_key

        doc_name = frappe.db.get_value("Automation Event", filters, "name")
        if not doc_name:
            return error_response("NOT_FOUND", "Automation Event not found.", status_code=404)

        event = frappe.get_doc("Automation Event", doc_name)
        return ok_response({
            "event_id": event.event_id,
            "event_type": event.event_type,
            "source": event.source,
            "processing_status": event.processing_status,
            "retry_count": event.retry_count,
            "created_at": str(event.created_at),
            "processed_at": str(event.processed_at) if event.processed_at else None,
            "error_details": event.error_details,
        })

    except AcomApiError as exc:
        return exc.to_response()
    except Exception as exc:
        frappe.log_error("get_event_status error", str(exc))
        return error_response("INTERNAL_ERROR", "Failed to get event status.", status_code=500)
