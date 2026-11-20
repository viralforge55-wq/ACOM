"""Tests for Automation Event DocType and Outbox Dispatcher (DATA_DICTIONARY §10, ADR-0002)."""

from __future__ import annotations

import json
import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime
from acom_core.integration_management.services.event_service import (
    dispatch_event,
    record_event,
    register_event_handler,
)


class TestAutomationEvent(IntegrationTestCase):
    IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Fiscal Year", "Item", "Currency", "User"]

    def setUp(self) -> None:
        frappe.set_user("Administrator")

    def test_outbox_event_creation_and_autoname(self) -> None:
        """Automation Event creates with generated UUID and Received status."""
        idem_key = f"test_event_create_{frappe.generate_hash(length=8)}"
        doc = record_event(
            event_type="test.ping",
            source="Agent",
            idempotency_key=idem_key,
            payload={"test": 123},
        )
        self.assertTrue(doc.name)
        self.assertEqual(doc.event_id, doc.name)
        self.assertEqual(doc.processing_status, "Received")
        self.assertEqual(doc.retry_count, 0)

    def test_duplicate_idempotency_key_blocks_insert(self) -> None:
        """Duplicate idempotency key raises 409 DUPLICATE_EVENT."""
        from acom_core.api.errors import AcomApiError

        idem_key = f"test_event_dup_{frappe.generate_hash(length=8)}"
        record_event(
            event_type="test.ping",
            source="Agent",
            idempotency_key=idem_key,
            payload={"test": 1},
        )

        with self.assertRaises(AcomApiError) as ctx:
            record_event(
                event_type="test.ping",
                source="Agent",
                idempotency_key=idem_key,
                payload={"test": 2},
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.code, "DUPLICATE_EVENT")

    def test_dispatch_event_success_and_completed_status(self) -> None:
        """Handler execution transitions event to Completed status."""
        executed = []

        def sample_handler(payload):
            executed.append(payload)
            return {"ok": True}

        register_event_handler("test.sample", sample_handler)

        idem_key = f"test_dispatch_succ_{frappe.generate_hash(length=8)}"
        doc = record_event(
            event_type="test.sample",
            source="Agent",
            idempotency_key=idem_key,
            payload={"foo": "bar"},
        )

        res = dispatch_event(doc.name)
        self.assertEqual(res["status"], "completed")
        self.assertEqual(len(executed), 1)

        reloaded = frappe.get_doc("Automation Event", doc.name)
        self.assertEqual(reloaded.processing_status, "Completed")
        self.assertIsNotNone(reloaded.processed_at)

    def test_dispatch_event_failure_and_exponential_backoff(self) -> None:
        """Failing handler marks status Failed, increments retry_count, schedules backoff."""
        def failing_handler(payload):
            raise ValueError("Simulated network timeout")

        register_event_handler("test.fail", failing_handler)

        idem_key = f"test_dispatch_fail_{frappe.generate_hash(length=8)}"
        doc = record_event(
            event_type="test.fail",
            source="Agent",
            idempotency_key=idem_key,
            payload={"attempt": 1},
        )

        res = dispatch_event(doc.name)
        self.assertEqual(res["status"], "Failed")

        reloaded = frappe.get_doc("Automation Event", doc.name)
        self.assertEqual(reloaded.processing_status, "Failed")
        self.assertEqual(reloaded.retry_count, 1)
        self.assertIsNotNone(reloaded.next_attempt_at)
        self.assertIn("Simulated network timeout", reloaded.error_details)

    def test_dispatch_event_dead_letter_after_5_retries(self) -> None:
        """5 consecutive failures mark the event Dead Letter."""
        def permanent_fail(payload):
            raise RuntimeError("Fatal downstream unrecoverable error")

        register_event_handler("test.perm_fail", permanent_fail)

        idem_key = f"test_perm_fail_{frappe.generate_hash(length=8)}"
        doc = record_event(
            event_type="test.perm_fail",
            source="Agent",
            idempotency_key=idem_key,
            payload={},
        )
        doc.retry_count = 4
        doc.save(ignore_permissions=True)

        res = dispatch_event(doc.name)
        self.assertEqual(res["status"], "Dead Letter")

        reloaded = frappe.get_doc("Automation Event", doc.name)
        self.assertEqual(reloaded.processing_status, "Dead Letter")
        self.assertEqual(reloaded.retry_count, 5)

    def test_cannot_delete_automation_event_on_trash(self) -> None:
        """Automation Event records cannot be deleted (DATA_DICTIONARY §10 rule)."""
        idem_key = f"test_nodelete_{frappe.generate_hash(length=8)}"
        doc = record_event(
            event_type="test.immutable",
            source="Agent",
            idempotency_key=idem_key,
            payload={},
        )

        # Ensure in_test is temporarily unset to verify production guard
        old_flag = frappe.flags.in_test
        try:
            frappe.flags.in_test = False
            with self.assertRaises(frappe.ValidationError):
                doc.delete()
        finally:
            frappe.flags.in_test = old_flag
