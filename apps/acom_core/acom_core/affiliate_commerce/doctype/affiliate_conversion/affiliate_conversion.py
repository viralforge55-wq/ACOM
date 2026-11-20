"""Controller for Affiliate Conversion DocType (DATA_DICTIONARY.md §4, W4).

Invariants enforced here:
- Exact Decimal money validation (`commission_amount >= 0`, `order_value >= 0`).
- Composite idempotency key `dedupe_key = "{affiliate_network}::{network_conversion_id}"`
  enforced via MariaDB unique index (FRAPPE_AGENT_RULES.md §4).
- Strict status transition state machine:
    Pending   -> Confirmed | Rejected
    Confirmed -> Paid | Rejected
    Paid      -> terminal (corrections must be a NEW Reversed row, never an edit)
    Rejected  -> terminal (cannot transition to Confirmed or Paid)
    Reversed  -> terminal (requires reversal_reason; original row retained)
- `Paid` requires a non-empty `payment_reference`.
- Core financial & identity fields are immutable after insert.
- Every status creation/transition appends an entry to `status_history`.
- Deletion is blocked outside automated tests (immutable financial audit trail).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

PAISA = Decimal("0.01")

VALID_COMMISSION_STATUSES = frozenset(
    {"Pending", "Confirmed", "Rejected", "Paid", "Reversed"}
)

ALLOWED_COMMISSION_TRANSITIONS: dict[str, frozenset[str]] = {
    "Pending": frozenset({"Pending", "Confirmed", "Rejected"}),
    "Confirmed": frozenset({"Confirmed", "Paid", "Rejected"}),
    "Paid": frozenset({"Paid"}),
    "Rejected": frozenset({"Rejected"}),
    "Reversed": frozenset({"Reversed"}),
}

IMMUTABLE_CORE_FIELDS = (
    "affiliate_network",
    "network_conversion_id",
    "dedupe_key",
    "conversion_date",
    "currency",
)


def parse_non_negative_decimal(value, field_label: str) -> Decimal:
    """Parse value into a non-negative finite Decimal quantized to paisa (0.01)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        frappe.throw(_("{0} is required.").format(field_label), frappe.ValidationError)
    if isinstance(value, bool):
        frappe.throw(_("{0} must be a valid decimal number.").format(field_label), frappe.ValidationError)
    try:
        dec = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError) as exc:
        frappe.throw(
            _("{0} must be a valid decimal number.").format(field_label),
            frappe.ValidationError,
        )
    if dec.is_nan() or dec.is_infinite():
        frappe.throw(_("{0} must be a finite number.").format(field_label), frappe.ValidationError)
    if dec < Decimal("0"):
        frappe.throw(_("{0} cannot be negative.").format(field_label), frappe.ValidationError)
    return dec.quantize(PAISA, rounding=ROUND_HALF_UP)


def build_dedupe_key(affiliate_network: str, network_conversion_id: str) -> str:
    return f"{affiliate_network.strip()}::{network_conversion_id.strip()}"


class AffiliateConversion(Document):
    def before_validate(self) -> None:
        if self.network_conversion_id:
            self.network_conversion_id = str(self.network_conversion_id).strip()
        if self.external_order_id:
            self.external_order_id = str(self.external_order_id).strip()
        if self.payment_reference:
            self.payment_reference = str(self.payment_reference).strip()
        if self.raw_subid:
            self.raw_subid = str(self.raw_subid).strip()
        if self.raw_product_sku:
            self.raw_product_sku = str(self.raw_product_sku).strip()
        if not self.currency:
            self.currency = "INR"
        if not self.commission_status:
            self.commission_status = "Pending"
        if not self.matched_by:
            self.matched_by = "Unmatched"

        if self.affiliate_network and self.network_conversion_id:
            self.dedupe_key = build_dedupe_key(
                self.affiliate_network, self.network_conversion_id
            )

        # Keep needs_manual_review consistent with matched_by
        self.needs_manual_review = 1 if self.matched_by == "Unmatched" else 0

    def validate(self) -> None:
        self._validate_amounts()
        self._validate_status_requirements()
        if self.is_new():
            self._append_initial_audit_log()
        else:
            self._validate_update_invariants()

    def _validate_amounts(self) -> None:
        comm = parse_non_negative_decimal(self.commission_amount, "Commission Amount")
        self.commission_amount = float(comm)

        if self.order_value is not None and self.order_value != "":
            order_val = parse_non_negative_decimal(self.order_value, "Order Value")
            self.order_value = float(order_val)

    def _validate_status_requirements(self) -> None:
        if self.commission_status not in VALID_COMMISSION_STATUSES:
            frappe.throw(
                _("Invalid Commission Status '{0}'.").format(self.commission_status),
                frappe.ValidationError,
            )

        if self.commission_status == "Paid" and not self.payment_reference:
            frappe.throw(
                _("Payment Reference is required when Commission Status is Paid."),
                frappe.ValidationError,
            )

        if self.commission_status == "Reversed":
            if not self.reversal_reason or not str(self.reversal_reason).strip():
                frappe.throw(
                    _("Reversal Reason is required when Commission Status is Reversed."),
                    frappe.ValidationError,
                )

    def _append_initial_audit_log(self) -> None:
        if not self.status_history:
            self.append(
                "status_history",
                {
                    "from_status": "",
                    "to_status": self.commission_status,
                    "changed_at": now_datetime(),
                    "changed_by": frappe.session.user,
                    "import_batch": self.import_batch,
                    "note": self.flags.get("status_change_note") or "Imported",
                },
            )

    def _validate_update_invariants(self) -> None:
        previous = frappe.db.get_value(
            "Affiliate Conversion",
            self.name,
            [*IMMUTABLE_CORE_FIELDS, "commission_amount", "commission_status"],
            as_dict=True,
        )
        if not previous:
            return

        for fieldname in IMMUTABLE_CORE_FIELDS:
            if str(previous.get(fieldname) or "") != str(self.get(fieldname) or ""):
                frappe.throw(
                    _("Field '{0}' is immutable on Affiliate Conversion.").format(fieldname),
                    frappe.ValidationError,
                )

        prev_amount = parse_non_negative_decimal(previous.get("commission_amount"), "Commission Amount")
        curr_amount = parse_non_negative_decimal(self.commission_amount, "Commission Amount")
        if prev_amount != curr_amount:
            frappe.throw(
                _(
                    "Commission Amount is immutable after import. "
                    "Record a Reversed conversion row for adjustments."
                ),
                frappe.ValidationError,
            )

        prev_status = previous.get("commission_status")
        new_status = self.commission_status
        allowed = ALLOWED_COMMISSION_TRANSITIONS.get(prev_status, frozenset())
        if new_status not in allowed:
            frappe.throw(
                _("Illegal commission status transition from '{0}' to '{1}'.").format(
                    prev_status, new_status
                ),
                frappe.ValidationError,
            )

        if prev_status != new_status:
            self.append(
                "status_history",
                {
                    "from_status": prev_status,
                    "to_status": new_status,
                    "changed_at": now_datetime(),
                    "changed_by": frappe.session.user,
                    "import_batch": self.flags.get("transition_import_batch") or self.import_batch,
                    "note": self.flags.get("status_change_note")
                    or f"Transition {prev_status} -> {new_status}",
                },
            )

    def on_trash(self) -> None:
        if not frappe.flags.in_test:
            frappe.throw(
                _("Affiliate Conversion records are immutable financial audit records and cannot be deleted."),
                frappe.ValidationError,
            )
