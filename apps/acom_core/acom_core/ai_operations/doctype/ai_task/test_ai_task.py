"""Unit & Integration tests for AI Task DocType (DATA_DICTIONARY §8, TEST_PLAN X1, X2, X5)."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from acom_core.ai_operations.doctype.ai_task.ai_task import (
    AITask,
    compute_canonical_input_hash,
)
from acom_core.ai_operations.services.task_service import (
    create_ai_task,
    record_ai_task_result,
)

IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Fiscal Year", "Item", "Currency", "User"]


class TestAITask(IntegrationTestCase):
    """Test AI Task state machine, deduplication, retry policy, and validation invariants."""

    def setUp(self) -> None:
        frappe.set_user("Administrator")

    def tearDown(self) -> None:
        frappe.set_user("Administrator")

    def test_canonical_hash_deterministic(self) -> None:
        """Hashing canonicalizes keys and spacing identically."""
        p1 = {"b": 2, "a": 1}
        p2 = {"a": 1, "b": 2}
        self.assertEqual(compute_canonical_input_hash(p1), compute_canonical_input_hash(p2))

    def test_task_creation_and_autoname(self) -> None:
        """Creating an AI Task assigns a UUID task_id and defaults."""
        res = create_ai_task(
            task_type="ProductResearch",
            agent_id="product_hunter",
            model="qwen2.5:3b",
            input_payload={"sku": "SKU-TEST-01", "cost": 100},
        )
        self.assertTrue(res["ok"])
        self.assertFalse(res["duplicate"])
        task_id = res["task_id"]

        doc = frappe.get_doc("AI Task", task_id)
        self.assertEqual(doc.status, "Queued")
        self.assertEqual(doc.retry_count, 0)
        self.assertEqual(doc.max_retries, 2)
        self.assertTrue(bool(doc.input_hash))

    def test_task_deduplication_within_ttl(self) -> None:
        """Identical input within TTL returns existing task (DATA_DICTIONARY §8)."""
        payload = {"sku": "DEDUPE-SKU-01", "category": "Home"}
        res1 = create_ai_task(
            task_type="ProductResearch",
            agent_id="product_hunter",
            model="qwen2.5:3b",
            input_payload=payload,
        )
        res2 = create_ai_task(
            task_type="ProductResearch",
            agent_id="product_hunter",
            model="qwen2.5:3b",
            input_payload=payload,
        )
        self.assertEqual(res1["task_id"], res2["task_id"])
        self.assertTrue(res2["duplicate"])

    def test_X1_schema_failure_marks_rejected(self) -> None:
        """Output failing schema is marked Rejected with output_validated = 0."""
        res = create_ai_task(
            task_type="ProductResearch",
            agent_id="product_hunter",
            model="qwen2.5:3b",
            input_payload={"sku": "TEST-FAIL-01"},
        )
        task_id = res["task_id"]

        # Submit malformed output missing required fields
        invalid_output = {"product_name": "Incomplete Product"}
        sub_res = record_ai_task_result(task_id, invalid_output)
        self.assertFalse(sub_res["ok"])
        self.assertEqual(sub_res["error_code"], "SCHEMA_INVALID")

        doc = frappe.get_doc("AI Task", task_id)
        self.assertEqual(doc.status, "Rejected")
        self.assertEqual(doc.output_validated, 0)
        self.assertEqual(doc.error_code, "SCHEMA_INVALID")

    def test_X1_succeeded_strictly_requires_output_validated_flag(self) -> None:
        """In accordance with DATA_DICTIONARY §8, status Succeeded requires output_validated=1."""
        doc = frappe.get_doc(
            {
                "doctype": "AI Task",
                "task_type": "ProductResearch",
                "agent_id": "product_hunter",
                "model": "qwen2.5:3b",
                "input_hash": "dummyhash123",
                "status": "Queued",
            }
        )
        doc.insert()

        doc.status = "Succeeded"
        doc.output_validated = 0
        with self.assertRaises(frappe.ValidationError):
            doc.save()

    def test_X5_retry_policy_exhaustion(self) -> None:
        """Retry increments retry_count until max_retries then marks Failed."""
        res = create_ai_task(
            task_type="Classification",
            agent_id="support_classifier",
            model="qwen2.5:3b",
            input_payload={"msg": "help me"},
        )
        task_id = res["task_id"]
        doc = frappe.get_doc("AI Task", task_id)

        # Attempt 1 fail
        doc.mark_failed("TIMEOUT", "Connection dropped")
        doc.reload()
        self.assertEqual(doc.retry_count, 1)
        self.assertEqual(doc.status, "Queued")

        # Attempt 2 fail
        doc.mark_failed("TIMEOUT", "Connection dropped again")
        doc.reload()
        self.assertEqual(doc.retry_count, 2)
        self.assertEqual(doc.status, "Queued")

        # Attempt 3 fail (exhaustion)
        doc.mark_failed("TIMEOUT", "Final failure")
        doc.reload()
        self.assertEqual(doc.status, "Failed")
        self.assertEqual(doc.error_code, "TIMEOUT")
