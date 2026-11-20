"""ACOM Core — AI Task DocType Controller.

Governs execution state, retry counters, schema validation flags,
and input deduplication per DATA_DICTIONARY §8 and ARCHITECTURE_RULES §1.1.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime

ALLOWED_STATUSES = (
    "Queued",
    "Running",
    "Succeeded",
    "Failed",
    "Rejected",
    "Timed Out",
)

ALLOWED_TASK_TYPES = (
    "ProductResearch",
    "ContentGeneration",
    "SupplierAnalysis",
    "Classification",
    "Report",
    "Reconciliation",
)


def compute_canonical_input_hash(payload: Any) -> str:
    """Compute deterministic SHA-256 hash of canonical input data."""
    if payload is None:
        payload = {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            pass
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AITask(Document):
    """AI Task document representing an isolated unit of AI work."""

    def autoname(self) -> None:
        if not self.task_id:
            self.task_id = str(uuid.uuid4())
        self.name = self.task_id

    def before_validate(self) -> None:
        if not self.task_id:
            self.task_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = now_datetime()
        if not self.correlation_id:
            self.correlation_id = str(uuid.uuid4())
        if not self.status:
            self.status = "Queued"
        if self.retry_count is None:
            self.retry_count = 0
        if self.max_retries is None:
            self.max_retries = 2

        # Auto-compute canonical input hash if not set
        if not self.input_hash and self.input_payload:
            self.input_hash = compute_canonical_input_hash(self.input_payload)

    def validate(self) -> None:
        if self.status not in ALLOWED_STATUSES:
            frappe.throw(
                _("Invalid status '{0}'. Must be one of: {1}").format(
                    self.status, ", ".join(ALLOWED_STATUSES)
                ),
                exc=frappe.ValidationError,
            )

        if self.task_type not in ALLOWED_TASK_TYPES:
            frappe.throw(
                _("Invalid task_type '{0}'. Must be one of: {1}").format(
                    self.task_type, ", ".join(ALLOWED_TASK_TYPES)
                ),
                exc=frappe.ValidationError,
            )

        # Status invariant enforcement
        if self.status == "Succeeded":
            if not self.output_validated:
                frappe.throw(
                    _("An AI Task cannot be marked 'Succeeded' without output_validated = 1 (DATA_DICTIONARY §8)."),
                    exc=frappe.ValidationError,
                )
            if not self.completed_at:
                self.completed_at = now_datetime()

        elif self.status == "Rejected":
            if self.output_validated:
                frappe.throw(
                    _("A rejected AI Task must have output_validated = 0."),
                    exc=frappe.ValidationError,
                )
            if not self.error_code:
                self.error_code = "SCHEMA_INVALID"
            if not self.completed_at:
                self.completed_at = now_datetime()

        elif self.status == "Running":
            if not self.started_at:
                self.started_at = now_datetime()

        elif self.status in ("Failed", "Timed Out"):
            if not self.completed_at:
                self.completed_at = now_datetime()

        # Compute duration_ms if timestamps are present
        if self.started_at and self.completed_at and not self.duration_ms:
            start_dt = get_datetime(self.started_at)
            end_dt = get_datetime(self.completed_at)
            delta = (end_dt - start_dt).total_seconds()
            if delta >= 0:
                self.duration_ms = int(delta * 1000)

    def mark_running(self) -> None:
        """Mark task as running and record start time."""
        self.status = "Running"
        self.started_at = now_datetime()
        self.save()

    def mark_succeeded(
        self,
        output_payload: Any,
        output_reference: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        """Transition task to Succeeded with verified output."""
        self.status = "Succeeded"
        self.output_validated = 1
        if isinstance(output_payload, (dict, list)):
            self.output_payload = json.dumps(output_payload)
        else:
            self.output_payload = output_payload
        if output_reference:
            self.output_reference = output_reference
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.completed_at = now_datetime()
        self.save()

    def mark_rejected(
        self,
        error_code: str = "SCHEMA_INVALID",
        error_details: str = "",
        output_payload: Any = None,
    ) -> None:
        """Transition task to Rejected on schema failure."""
        self.status = "Rejected"
        self.output_validated = 0
        self.error_code = error_code
        self.error_details = error_details[:500] if error_details else ""
        if output_payload is not None:
            if isinstance(output_payload, (dict, list)):
                self.output_payload = json.dumps(output_payload)
            else:
                self.output_payload = str(output_payload)
        self.completed_at = now_datetime()
        self.save()

    def mark_failed(self, error_code: str, error_details: str) -> None:
        """Transition task to Failed or increment retry count."""
        if self.retry_count < self.max_retries:
            self.retry_count += 1
            self.status = "Queued"
            self.error_code = error_code
            self.error_details = f"Attempt {self.retry_count} failed: {error_details}"[:500]
        else:
            self.status = "Failed"
            self.error_code = error_code
            self.error_details = f"Max retries ({self.max_retries}) exhausted: {error_details}"[:500]
            self.completed_at = now_datetime()
        self.save()

    def mark_timed_out(self, error_details: str = "Inference request timed out") -> None:
        """Transition task to Timed Out."""
        if self.retry_count < self.max_retries:
            self.retry_count += 1
            self.status = "Queued"
            self.error_code = "TIMED_OUT"
            self.error_details = f"Attempt {self.retry_count} timed out: {error_details}"[:500]
        else:
            self.status = "Timed Out"
            self.error_code = "TIMED_OUT"
            self.error_details = f"Max retries exhausted after timeout: {error_details}"[:500]
            self.completed_at = now_datetime()
        self.save()
