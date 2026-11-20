"""Workflow 3: Supplier Stock & Price Monitor (MASTER_BLUEPRINT §11, BUSINESS_WORKFLOWS W8).

Flow:
1. Scheduled / event-driven check over Dropshipping Product catalog against supplier feed.
2. Detects stock-outs: marks supplier_stock = 0 and sync_status = Out of Stock.
3. Detects price increases: recomputes contribution margin.
   If margin compresses below threshold (15%) or profit <= 0, raises an AI Approval Request
   for founder pricing review.
4. Financial Firewall: NEVER auto-updates customer-facing retail price without approval.
5. Emits Automation Event (supplier_monitor.completed or supplier_monitor.alert).
6. Failure path: corrupt/malformed feed handled atomically, logged in Automation Event.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List

import frappe
from frappe.utils import now_datetime
from acom_core.api.errors import AcomApiError
from acom_core.product_intelligence.margin import calculate_contribution_profit
from acom_core.integration_management.services.event_service import record_event


def run_supplier_monitor_flow(
    *,
    feed_items: List[Dict[str, Any]],
    idempotency_key: str | None = None,
) -> Dict[str, Any]:
    """Execute Flow 3: Supplier Stock & Price Monitor."""
    if not isinstance(feed_items, list):
        raise AcomApiError("VALIDATION_ERROR", "feed_items must be a list of supplier items.", status_code=400)

    idem_key = idempotency_key or f"supplier_mon::{int(now_datetime().timestamp())}"

    updated_count = 0
    alerts_raised = []
    errors = []

    for item in feed_items:
        supplier_sku = item.get("supplier_sku")
        if not supplier_sku:
            errors.append({"item": item, "error": "Missing supplier_sku"})
            continue

        stock = item.get("stock")
        cost = item.get("cost")

        if stock is not None and stock < 0:
            errors.append({"supplier_sku": supplier_sku, "error": "Negative stock is invalid"})
            continue

        # Find matching Dropshipping Product
        prod_names = frappe.get_all(
            "Dropshipping Product",
            filters={"supplier_sku": supplier_sku},
            pluck="name",
        )

        for prod_name in prod_names:
            doc = frappe.get_doc("Dropshipping Product", prod_name)
            needs_save = False

            # Update stock
            if stock is not None:
                doc.supplier_stock = stock
                doc.last_stock_sync = now_datetime()
                if stock == 0:
                    doc.status = "Out of Stock"
                needs_save = True

            # Check cost / margin compression
            if cost is not None and cost > 0:
                old_cost = doc.supplier_cost or Decimal("0")
                new_cost = Decimal(str(cost))

                if new_cost != old_cost:
                    # Recompute margin
                    margin_res = calculate_contribution_profit(
                        selling_price=doc.selling_price,
                        supplier_cost=new_cost,
                        shipping_cost=doc.shipping_cost or Decimal("0"),
                        packaging_cost=doc.packaging_cost or Decimal("0"),
                        payment_fee_percent=doc.payment_fee_percent or Decimal("2.0"),
                        expected_return_rate=doc.expected_return_rate or Decimal("5.0"),
                    )

                    if margin_res.contribution_profit <= Decimal("0") or margin_res.contribution_margin_pct < Decimal("15.0"):
                        # Raise high-risk approval request for founder price review
                        from datetime import timedelta
                        req_id = f"aireq-margin-{frappe.generate_hash(length=8)}"
                        approval_req = frappe.get_doc({
                            "doctype": "AI Approval Request",
                            "request_id": req_id,
                            "action_type": "PriceChange",
                            "approval_status": "Pending",
                            "risk_level": "High",
                            "related_doctype": "Dropshipping Product",
                            "related_name": doc.name,
                            "recommendation": (
                                f"Supplier cost for '{doc.product_name}' increased from ₹{old_cost} to ₹{new_cost}. "
                                f"Margin compressed to {margin_res.contribution_margin_pct:.1f}% (Profit ₹{margin_res.contribution_profit}). "
                                f"Review retail price ₹{doc.selling_price}."
                            ),
                            "rationale": f"Automated supplier feed sync detected price increase. Selling price unchanged pending review.",
                            "estimated_financial_impact": float(margin_res.contribution_profit),
                            "expires_at": now_datetime() + timedelta(days=3),
                        })
                        approval_req.insert(ignore_permissions=True)
                        alerts_raised.append({
                            "product": doc.name,
                            "approval_request": approval_req.name,
                            "new_margin_pct": str(margin_res.contribution_margin_pct),
                        })

                    # Record updated supplier cost on draft sync note, but DO NOT change selling_price
                    doc.supplier_cost = new_cost
                    needs_save = True

            if needs_save:
                doc.save(ignore_permissions=True)
                updated_count += 1

    event_type = "supplier_monitor.alert" if alerts_raised else "supplier_monitor.completed"
    if errors and updated_count == 0:
        event_type = "supplier_monitor.failed"

    summary_payload = {
        "items_checked": len(feed_items),
        "updated_count": updated_count,
        "alerts_count": len(alerts_raised),
        "alerts": alerts_raised,
        "errors": errors,
    }

    event = record_event(
        event_type=event_type,
        source="Scheduler",
        idempotency_key=idem_key,
        payload=summary_payload,
        allow_duplicate_return=True,
    )

    return {
        "ok": len(errors) == 0 or updated_count > 0,
        "event_id": event.event_id,
        "event_type": event_type,
        "updated_count": updated_count,
        "alerts_count": len(alerts_raised),
        "errors_count": len(errors),
    }
