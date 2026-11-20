"""Downstream ERPNext execution, PO approval, tracking & refund workflow (Blueprint §9, E5, W5–W6).

Invariants:
- Reuses ERPNext Customer, Sales Order, and Purchase Order (zero parallel accounting engine).
- Upon verified payment outbox event: submits ERPNext Sales Order and generates supplier
  Purchase Order in DRAFT (`docstatus = 0`) — NEVER auto-submits PO!
- PO submission requires explicit authorized approval (`System Manager`, `ACOM Finance`, `ACOM Manager`).
- Refunds require explicit authorized approval (`System Manager`, `ACOM Finance` ONLY).
- Zero manual `frappe.db.commit()`, zero raw SQL.
"""

from __future__ import annotations

import json
import hashlib
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import frappe
from frappe.utils import add_days, now_datetime, nowdate

from acom_core.api.errors import AcomApiError, format_money
from acom_core.dropshipping_commerce.services.payment_gateway import create_test_gateway_refund

PAISA = Decimal("0.01")
PO_APPROVER_ROLES = frozenset({"System Manager", "ACOM Finance", "ACOM Manager"})
FULFILLMENT_ROLES = frozenset({"System Manager", "ACOM Manager"})
REFUND_APPROVER_ROLES = frozenset({"System Manager", "ACOM Finance"})


def _default_company_and_warehouse() -> tuple[str, str]:
    company = (
        frappe.db.get_single_value("Global Defaults", "default_company")
        or frappe.db.get_value("Company", {}, "name", order_by="creation asc")
    )
    if not company:
        raise RuntimeError("No default Company configured in ERPNext.")
    warehouse = frappe.db.get_value(
        "Warehouse", {"company": company, "is_group": 0}, "name", order_by="creation asc"
    )
    if not warehouse:
        raise RuntimeError(f"No leaf Warehouse configured for company '{company}'.")
    return company, warehouse


def _resolve_or_create_erp_customer(*, name: str, email: str, user: str) -> str:
    """Reuse ERPNext Customer master rather than inventing a second customer table."""
    identity = "ACOM-" + hashlib.sha256(user.encode()).hexdigest()[:24]
    existing = frappe.db.get_value("Customer", {"customer_name": identity}, "name")
    if existing:
        return existing

    cust_group = (
        frappe.db.get_value("Customer Group", {"is_group": 0}, "name", order_by="name asc")
        or "Commercial"
    )
    territory = (
        frappe.db.get_value("Territory", {"name": "India"}, "name")
        or frappe.db.get_value("Territory", {"is_group": 0}, "name", order_by="name asc")
        or "All Territories"
    )
    doc = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": identity,
            "customer_type": "Individual",
            "customer_group": cust_group,
            "territory": territory,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def process_payment_confirmed_event(event_name: str) -> dict[str, Any]:
    """Internal worker entrypoint; never whitelisted or callable by storefront."""
    original_user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        return _process_payment_confirmed_event(event_name)
    finally:
        frappe.set_user(original_user)


def _process_payment_confirmed_event(event_name: str) -> dict[str, Any]:
    """Consume `payment.confirmed` outbox event: submit ERPNext SO + create Draft PO (E5).

    Idempotent: if `checkout.sales_order` is already linked, skips creation cleanly.
    If ERP creation raises, marks event `Failed` and checkout `ERP_PENDING` without
    losing the confirmed payment record (TEST_PLAN P8).
    """
    frappe.db.get_value("Automation Event", event_name, "name", for_update=True)
    event = frappe.get_doc("Automation Event", event_name)
    if event.event_type != "payment.confirmed":
        raise ValueError("Expected a verified payment event")
    if event.processing_status == "Completed":
        payload_data = json.loads(event.payload) if isinstance(event.payload, str) else event.payload
        return {"event_id": event.name, "status": "Completed", "checkout_id": payload_data.get("checkout_id")}

    event.processing_status = "Processing"
    event.save(ignore_permissions=True)

    payload = json.loads(event.payload) if isinstance(event.payload, str) else event.payload
    checkout_id = payload["checkout_id"]
    frappe.db.get_value("Dropship Checkout", checkout_id, "name", for_update=True)
    checkout = frappe.get_doc("Dropship Checkout", checkout_id)
    if not checkout.gateway_payment_id or not checkout.paid_at:
        raise ValueError("Verified capture required before ERP execution")
    if checkout.status in {"Cancelled", "Refunded"} or checkout.refund_status == "Requested":
        raise ValueError("Order is held for cancellation/refund review")

    # Idempotency guard: already synced to ERPNext -> never create duplicate SO/PO
    if checkout.sales_order:
        event.processing_status = "Completed"
        event.processed_at = now_datetime()
        event.save(ignore_permissions=True)
        return {
            "event_id": event.name,
            "checkout_id": checkout.name,
            "sales_order": checkout.sales_order,
            "purchase_order": checkout.purchase_order,
            "status": "Completed",
        }

    frappe.db.savepoint("acom_erp_execution")
    try:
        # Lock in deterministic order to prevent concurrent captures overselling stock.
        for row in sorted(checkout.items, key=lambda row: row.dropshipping_product):
            frappe.db.get_value("Dropshipping Product", row.dropshipping_product, "name", for_update=True)
            product = frappe.get_doc("Dropshipping Product", row.dropshipping_product)
            if product.status != "Published" or product.supplier_stock < row.quantity:
                raise ValueError("Supplier stock unavailable after payment; refund review required")
            product.supplier_stock -= row.quantity
            if product.supplier_stock == 0:
                product.status = "Out of Stock"
            product.save(ignore_permissions=True)
        company, warehouse = _default_company_and_warehouse()
        erp_customer = _resolve_or_create_erp_customer(
            name=checkout.customer_name,
            email=checkout.customer_email,
            user=checkout.customer_user,
        )

        delivery_date = add_days(nowdate(), 5)
        so = frappe.get_doc(
            {
                "doctype": "Sales Order",
                "customer": erp_customer,
                "company": company,
                "transaction_date": nowdate(),
                "delivery_date": delivery_date,
                "po_no": checkout.name,
                "order_type": "Sales",
                "currency": checkout.currency or "INR",
                "selling_price_list": "Standard Selling",
                "items": [
                    {
                        "item_code": row.erpnext_item,
                        "qty": int(row.quantity),
                        "rate": float(row.unit_price),
                        "warehouse": warehouse,
                        "delivery_date": delivery_date,
                    }
                    for row in checkout.items
                ],
            }
        )
        so.flags.ignore_permissions = True
        so.insert(ignore_permissions=True)
        if Decimal(str(so.grand_total)).quantize(PAISA) != Decimal(str(checkout.grand_total)).quantize(PAISA):
            raise ValueError("ERPNext total differs from captured total; held for reconciliation")
        so.submit()

        # Group items by supplier and generate exactly one DRAFT Purchase Order per supplier (E5).
        by_supplier: dict[str, list] = {}
        for row in checkout.items:
            by_supplier.setdefault(row.supplier, []).append(row)

        created_pos: list[str] = []
        for supplier, supplier_rows in by_supplier.items():
            po = frappe.get_doc(
                {
                    "doctype": "Purchase Order",
                    "supplier": supplier,
                    "company": company,
                    "transaction_date": nowdate(),
                    "schedule_date": delivery_date,
                    "currency": checkout.currency or "INR",
                    "buying_price_list": "Standard Buying",
                    "items": [
                        {
                            "item_code": row.erpnext_item,
                            "qty": int(row.quantity),
                            "rate": float(row.supplier_cost),
                            "warehouse": warehouse,
                            "schedule_date": delivery_date,
                            "sales_order": so.name,
                        }
                        for row in supplier_rows
                    ],
                }
            )
            # Explicitly remain DRAFT (docstatus = 0); NEVER auto-submit without approval!
            po.insert(ignore_permissions=True)
            created_pos.append(po.name)

        checkout.sales_order = so.name
        checkout.purchase_order = created_pos[0] if created_pos else None
        checkout.status = "AwaitingSupplier"
        checkout.erp_sync_status = "Synced"
        checkout.save(ignore_permissions=True)

        event.processing_status = "Completed"
        event.processed_at = now_datetime()
        event.error_details = ""
        event.save(ignore_permissions=True)

        return {
            "event_id": event.name,
            "checkout_id": checkout.name,
            "sales_order": so.name,
            "purchase_orders": created_pos,
            "status": "Completed",
        }
    except Exception as exc:
        # Keep the committed capture, but discard every partial Customer/SO/PO write.
        frappe.db.rollback(save_point="acom_erp_execution")
        checkout.reload()
        checkout.erp_sync_status = "ERP_PENDING"
        checkout.save(ignore_permissions=True)

        event.reload()
        event.processing_status = "Failed" if int(event.retry_count or 0) < 4 else "Dead Letter"
        event.retry_count = int(event.retry_count or 0) + 1
        from frappe.utils import add_to_date
        event.next_attempt_at = add_to_date(now_datetime(), seconds=60 * 2 ** event.retry_count)
        event.error_details = type(exc).__name__
        event.save(ignore_permissions=True)
        frappe.log_error(title=f"ACOM ERP sync failed for {checkout.name}", message=frappe.get_traceback())

        return {
            "event_id": event.name,
            "checkout_id": checkout.name,
            "erp_sync_status": "ERP_PENDING",
            "status": "Failed",
        }


def approve_and_submit_purchase_order(*, checkout_id: str, note: str = "") -> dict[str, Any]:
    """Authorized founder/finance approval to submit the supplier Draft Purchase Order."""
    if frappe.session.user == "Guest":
        raise AcomApiError("UNAUTHENTICATED", "Authentication required.", status_code=401)
    if not set(frappe.get_roles(frappe.session.user)).intersection(PO_APPROVER_ROLES):
        raise AcomApiError("FORBIDDEN", "Not permitted to approve Purchase Orders.", status_code=403)

    if not frappe.db.exists("Dropship Checkout", checkout_id):
        raise AcomApiError("NOT_FOUND", "Checkout not found.", status_code=404)

    frappe.db.get_value("Dropship Checkout", checkout_id, "name", for_update=True)
    checkout = frappe.get_doc("Dropship Checkout", checkout_id)
    if not checkout.purchase_order:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "No Draft Purchase Order is linked to this checkout.",
            status_code=422,
        )

    if checkout.status not in {"AwaitingSupplier", "Processing"} or checkout.refund_status == "Requested":
        raise AcomApiError("VALIDATION_ERROR", "Order is not eligible for supplier approval.", status_code=422)
    po = frappe.get_doc("Purchase Order", checkout.purchase_order)
    if po.docstatus == 1:
        return {
            "checkout_id": checkout.name,
            "purchase_order": po.name,
            "docstatus": po.docstatus,
            "status": checkout.status,
            "already_submitted": True,
        }
    if po.docstatus != 0:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Linked Purchase Order is cancelled and cannot be submitted.",
            status_code=422,
        )

    po.flags.ignore_permissions = True
    po.submit()
    po.add_comment("Comment", f"Approved by {frappe.session.user}: {(note or '').strip()}")
    for other_name in linked_purchase_orders(checkout):
        if other_name == po.name:
            continue
        other = frappe.get_doc("Purchase Order", other_name)
        if other.docstatus == 0:
            other.flags.ignore_permissions = True
            other.submit()
            other.add_comment("Comment", f"Approved by {frappe.session.user}: {(note or '').strip()}")
    checkout.status = "Processing"
    checkout.save(ignore_permissions=True)

    return {
        "checkout_id": checkout.name,
        "purchase_order": po.name,
        "docstatus": po.docstatus,
        "status": checkout.status,
        "approved_by": frappe.session.user,
        "note": (note or "").strip(),
    }


def update_fulfillment_tracking(
    *,
    checkout_id: str,
    carrier: str,
    tracking_number: str,
    tracking_url: str = "",
    estimated_delivery: str | None = None,
    status: str = "Shipped",
) -> dict[str, Any]:
    """Update supplier shipment tracking and fulfillment status (Shipped / Delivered)."""
    if frappe.session.user == "Guest":
        raise AcomApiError("UNAUTHENTICATED", "Authentication required.", status_code=401)
    if not set(frappe.get_roles(frappe.session.user)).intersection(FULFILLMENT_ROLES):
        raise AcomApiError("FORBIDDEN", "Not permitted to update fulfillment tracking.", status_code=403)

    if status not in ("Shipped", "Delivered"):
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Fulfillment status must be Shipped or Delivered.",
            status_code=400,
            details={"fields": ["status"]},
        )

    if not frappe.db.exists("Dropship Checkout", checkout_id):
        raise AcomApiError("NOT_FOUND", "Checkout not found.", status_code=404)

    checkout = frappe.get_doc("Dropship Checkout", checkout_id)
    if checkout.status not in ("Processing", "Shipped", "Delivered") or checkout.refund_status == "Requested":
        raise AcomApiError(
            "VALIDATION_ERROR",
            f"Cannot update tracking while checkout is '{checkout.status}'.",
            status_code=422,
        )

    checkout.carrier = (carrier or "").strip()
    checkout.tracking_number = (tracking_number or "").strip()
    checkout.tracking_url = (tracking_url or "").strip()
    if checkout.tracking_url and not checkout.tracking_url.startswith("https://"):
        raise AcomApiError("VALIDATION_ERROR", "Tracking URL must use HTTPS.", status_code=400)
    if estimated_delivery:
        checkout.estimated_delivery = estimated_delivery
    checkout.status = status
    checkout.save(ignore_permissions=True)

    return {
        "checkout_id": checkout.name,
        "status": checkout.status,
        "carrier": checkout.carrier,
        "tracking_number": checkout.tracking_number,
        "tracking_url": checkout.tracking_url,
        "estimated_delivery": str(checkout.estimated_delivery or ""),
    }


def request_cancellation_or_refund(
    *,
    checkout_id: str,
    reason: str,
    refund_amount: str | None = None,
) -> dict[str, Any]:
    """Cancel an unpaid checkout OR open an approval-gated refund request on a paid order."""
    if frappe.session.user == "Guest":
        raise AcomApiError("UNAUTHENTICATED", "Authentication required.", status_code=401)

    if not (reason or "").strip():
        raise AcomApiError(
            "VALIDATION_ERROR",
            "reason is required.",
            status_code=400,
            details={"fields": ["reason"]},
        )

    if not frappe.db.exists("Dropship Checkout", checkout_id):
        raise AcomApiError("FORBIDDEN", "Not permitted.", status_code=403)

    checkout = frappe.get_doc("Dropship Checkout", checkout_id)
    is_privileged = bool(set(frappe.get_roles(frappe.session.user)).intersection(PO_APPROVER_ROLES))
    if checkout.customer_user != frappe.session.user and not is_privileged:
        raise AcomApiError("FORBIDDEN", "Not permitted.", status_code=403)

    if checkout.status in ("Cancelled", "Refunded"):
        raise AcomApiError(
            "VALIDATION_ERROR",
            f"Checkout is already '{checkout.status}'.",
            status_code=422,
        )

    if checkout.status == "PendingPayment":
        checkout.status = "Cancelled"
        checkout.refund_reason = reason.strip()
        checkout.save(ignore_permissions=True)
        return {
            "checkout_id": checkout.name,
            "status": checkout.status,
            "refund_status": "None",
        }

    grand_total = Decimal(str(checkout.grand_total)).quantize(PAISA, rounding=ROUND_HALF_UP)
    req_amount = grand_total
    if refund_amount is not None and str(refund_amount).strip():
        try:
            req_amount = Decimal(str(refund_amount).strip()).quantize(PAISA, rounding=ROUND_HALF_UP)
        except Exception as exc:
            raise AcomApiError(
                "VALIDATION_ERROR",
                "refund_amount must be a valid decimal.",
                status_code=400,
                details={"fields": ["refund_amount"]},
            ) from exc
    if req_amount <= Decimal("0.00") or req_amount > grand_total:
        raise AcomApiError(
            "VALIDATION_ERROR",
            f"refund_amount must be > 0 and <= captured amount ({grand_total}).",
            status_code=422,
            details={"fields": ["refund_amount"]},
        )

    # Hold fulfillment using refund_status; preserve the ERP fulfillment state.
    checkout.refund_status = "Requested"
    checkout.refund_amount = float(req_amount)
    checkout.refund_reason = reason.strip()
    checkout.save(ignore_permissions=True)

    return {
        "checkout_id": checkout.name,
        "status": checkout.status,
        "refund_status": checkout.refund_status,
        "refund_amount": format_money(req_amount, checkout.currency or "INR"),
    }


def approve_or_reject_refund(
    *,
    checkout_id: str,
    decision: str,
    note: str = "",
) -> dict[str, Any]:
    """Authorized approval gate for refunds (System Manager / ACOM Finance ONLY — W6)."""
    if frappe.session.user == "Guest":
        raise AcomApiError("UNAUTHENTICATED", "Authentication required.", status_code=401)
    if not set(frappe.get_roles(frappe.session.user)).intersection(REFUND_APPROVER_ROLES):
        raise AcomApiError("FORBIDDEN", "Not permitted to approve refunds.", status_code=403)

    clean_decision = (decision or "").strip()
    if clean_decision not in ("Approved", "Rejected"):
        raise AcomApiError(
            "VALIDATION_ERROR",
            "decision must be 'Approved' or 'Rejected'.",
            status_code=400,
            details={"fields": ["decision"]},
        )
    if clean_decision == "Rejected" and not (note or "").strip():
        raise AcomApiError(
            "VALIDATION_ERROR",
            "note is required when rejecting a refund request.",
            status_code=400,
            details={"fields": ["note"]},
        )

    if not frappe.db.exists("Dropship Checkout", checkout_id):
        raise AcomApiError("NOT_FOUND", "Checkout not found.", status_code=404)

    frappe.db.get_value("Dropship Checkout", checkout_id, "name", for_update=True)
    checkout = frappe.get_doc("Dropship Checkout", checkout_id)
    if checkout.refund_status != "Requested":
        raise AcomApiError(
            "VALIDATION_ERROR",
            f"Checkout refund_status is '{checkout.refund_status}', expected 'Requested'.",
            status_code=422,
        )

    if clean_decision == "Rejected":
        checkout.refund_status = "Rejected"
        checkout.refund_approved_by = frappe.session.user
        checkout.save(ignore_permissions=True)
        return {
            "checkout_id": checkout.name,
            "status": checkout.status,
            "refund_status": checkout.refund_status,
            "decided_by": frappe.session.user,
        }

    # Approved: execute test-mode gateway refund, record outbox event, mark Refunded
    refund_amt = Decimal(str(checkout.refund_amount)).quantize(PAISA, rounding=ROUND_HALF_UP)
    gw_refund = create_test_gateway_refund(
        payment_id=checkout.gateway_payment_id or checkout.gateway_order_ref,
        amount_str=f"{refund_amt:.2f}",
        currency=checkout.currency or "INR",
    )

    checkout.status = "Refunded"
    checkout.refund_status = "Processed"
    checkout.refund_approved_by = frappe.session.user
    checkout.refund_gateway_ref = gw_refund["refund_ref"]
    checkout.save(ignore_permissions=True)

    # Record immutable outbox event for refund reconciliation
    evt = frappe.get_doc(
        {
            "doctype": "Automation Event",
            "event_id": str(uuid.uuid4()),
            "event_type": "refund.processed",
            "source": "PaymentGateway",
            "aggregate_doctype": "Dropship Checkout",
            "aggregate_name": checkout.name,
            "idempotency_key": f"refund::{checkout.name}::{gw_refund['refund_ref']}",
            "payload": json.dumps(
                {
                    "checkout_id": checkout.name,
                    "sales_order": checkout.sales_order,
                    "refund_ref": gw_refund["refund_ref"],
                    "amount": f"{refund_amt:.2f}",
                    "currency": checkout.currency or "INR",
                    "approved_by": frappe.session.user,
                }
            ),
            "processing_status": "Completed",
            "processed_at": now_datetime(),
        }
    )
    evt.insert(ignore_permissions=True)

    return {
        "checkout_id": checkout.name,
        "status": checkout.status,
        "refund_status": checkout.refund_status,
        "refund_gateway_ref": checkout.refund_gateway_ref,
        "refund_amount": format_money(refund_amt, checkout.currency or "INR"),
        "approved_by": frappe.session.user,
    }


def linked_purchase_orders(checkout):
    if not checkout.sales_order:
        return []
    return sorted(set(frappe.get_all("Purchase Order Item", filters={"sales_order": checkout.sales_order}, pluck="parent")))
