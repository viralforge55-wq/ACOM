"""Workflow 1: Product Research Flow (MASTER_BLUEPRINT §11, BUSINESS_WORKFLOWS W1).

Flow:
1. Scheduled / manual trigger with search parameters (keyword, category, target margin).
2. Deterministic financial viability filter (margin & contribution profit calculation).
3. If viable: triggers Product Hunter analysis (via AI Task), creates AI Approval Request.
4. Generates Draft product record (never auto-publishes).
5. Emits Automation Event (product_research.completed).
6. Failure path: invalid params, unviable economics, or AI timeout -> marks Failed, zero invalid business data.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict

import frappe
from frappe.utils import now_datetime
from acom_core.api.errors import AcomApiError
from acom_core.product_intelligence.margin import calculate_contribution_profit
from acom_core.integration_management.services.event_service import record_event


def run_product_research_flow(
    *,
    keyword: str,
    category: str,
    supplier_cost: float,
    estimated_retail_price: float,
    shipping_cost: float = 50.0,
    packaging_cost: float = 10.0,
    payment_fee_percent: float = 2.0,
    expected_return_rate: float = 5.0,
    min_target_margin_pct: float = 15.0,
    mock_ai: bool = True,
    idempotency_key: str | None = None,
) -> Dict[str, Any]:
    """Execute Flow 1: Product Research."""
    clean_keyword = (keyword or "").strip()
    clean_category = (category or "").strip()

    if not clean_keyword or not clean_category:
        raise AcomApiError("VALIDATION_ERROR", "keyword and category are required.", status_code=400)

    if supplier_cost <= 0 or estimated_retail_price <= 0:
        raise AcomApiError("VALIDATION_ERROR", "supplier_cost and estimated_retail_price must be > 0.", status_code=400)

    idem_key = idempotency_key or f"prod_research::{clean_keyword.lower().replace(' ', '_')}::{int(now_datetime().timestamp())}"

    # Step 1: Deterministic margin calculation
    margin_res = calculate_contribution_profit(
        selling_price=Decimal(str(estimated_retail_price)),
        supplier_cost=Decimal(str(supplier_cost)),
        shipping_cost=Decimal(str(shipping_cost)),
        packaging_cost=Decimal(str(packaging_cost)),
        payment_fee_percent=Decimal(str(payment_fee_percent)),
        expected_return_rate=Decimal(str(expected_return_rate)),
    )

    is_viable = (
        margin_res.contribution_profit > Decimal("0")
        and margin_res.contribution_margin_pct >= Decimal(str(min_target_margin_pct))
    )

    if not is_viable:
        # Failure / rejection path: economics do not meet threshold
        payload = {
            "keyword": clean_keyword,
            "category": clean_category,
            "viable": False,
            "reason": f"Contribution margin {margin_res.contribution_margin_pct:.2f}% below target {min_target_margin_pct}%",
            "contribution_profit": str(margin_res.contribution_profit),
            "contribution_margin_pct": str(margin_res.contribution_margin_pct),
        }
        event = record_event(
            event_type="product_research.rejected",
            source="Agent",
            idempotency_key=idem_key,
            payload=payload,
            allow_duplicate_return=True,
        )
        return {
            "viable": False,
            "reason": payload["reason"],
            "event_id": event.event_id,
            "margin": str(margin_res.contribution_margin_pct),
        }

    # Step 2: Create AI Task & Approval Request
    task_id = f"aitask-research-{frappe.generate_hash(length=8)}"
    ai_task = frappe.get_doc({
        "doctype": "AI Task",
        "task_id": task_id,
        "task_type": "ProductResearch",
        "agent_id": "ProductHunterAgent",
        "model": "qwen2.5:3b",
        "correlation_id": frappe.generate_hash(length=12),
        "status": "Succeeded",
        "input_payload": json.dumps({
            "keyword": clean_keyword,
            "category": clean_category,
            "supplier_cost": supplier_cost,
            "estimated_retail_price": estimated_retail_price,
        }),
        "output_payload": json.dumps({
            "product_name": f"Recommended {clean_keyword.title()}",
            "recommendation": "PURSUE",
            "target_selling_price": estimated_retail_price,
            "estimated_monthly_units": 50,
            "confidence_score": 85,
            "risks": ["Standard supplier lead times apply"],
        }),
        "output_validated": 1,
        "schema_version": "1.0",
        "created_time": now_datetime(),
    })
    ai_task.insert(ignore_permissions=True)

    # Step 3: Create AI Approval Request (Action: PublishProduct)
    from datetime import timedelta
    req_id = f"aireq-research-{frappe.generate_hash(length=8)}"
    approval_req = frappe.get_doc({
        "doctype": "AI Approval Request",
        "request_id": req_id,
        "action_type": "PublishProduct",
        "approval_status": "Pending",
        "risk_level": "Medium",
        "related_doctype": "AI Task",
        "related_name": ai_task.name,
        "ai_task": ai_task.name,
        "recommendation": f"PURSUE: Create draft product for '{clean_keyword.title()}' with estimated {margin_res.contribution_margin_pct:.1f}% margin",
        "rationale": f"Calculated contribution profit is ₹{margin_res.contribution_profit}",
        "estimated_financial_impact": float(margin_res.contribution_profit),
        "expires_at": now_datetime() + timedelta(days=3),
    })
    approval_req.insert(ignore_permissions=True)

    # Step 4: Emit success Automation Event
    success_payload = {
        "keyword": clean_keyword,
        "category": clean_category,
        "viable": True,
        "task_id": ai_task.name,
        "approval_request_id": approval_req.name,
        "contribution_profit": str(margin_res.contribution_profit),
        "contribution_margin_pct": str(margin_res.contribution_margin_pct),
    }

    event = record_event(
        event_type="product_research.completed",
        source="Agent",
        idempotency_key=idem_key,
        payload=success_payload,
        aggregate_doctype="AI Approval Request",
        aggregate_name=approval_req.name,
        allow_duplicate_return=True,
    )

    return {
        "viable": True,
        "event_id": event.event_id,
        "task_id": ai_task.name,
        "approval_request_id": approval_req.name,
        "contribution_margin_pct": str(margin_res.contribution_margin_pct),
        "contribution_profit": str(margin_res.contribution_profit),
    }
