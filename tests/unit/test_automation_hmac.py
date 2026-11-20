"""Unit tests for M2M HMAC signature generation and security validation."""

from __future__ import annotations

import time
import unittest
from automation.security import (
    DEFAULT_LOCAL_HMAC_SECRET,
    compute_hmac_signature,
    generate_hmac_headers,
)


class TestAutomationHMAC(unittest.TestCase):
    def setUp(self) -> None:
        self.secret = DEFAULT_LOCAL_HMAC_SECRET

    def test_generate_hmac_headers_structure(self) -> None:
        """Header dictionary contains signature and timestamp."""
        payload = b'{"event": "test.ping"}'
        headers = generate_hmac_headers(payload, secret=self.secret)

        self.assertIn("X-ACOM-Signature", headers)
        self.assertIn("X-ACOM-Timestamp", headers)
        self.assertEqual(len(headers["X-ACOM-Signature"]), 64)  # 64 hex characters for SHA-256
        self.assertTrue(headers["X-ACOM-Timestamp"].isdigit())

    def test_deterministic_signature(self) -> None:
        """Same payload, secret, and timestamp produce identical signature."""
        payload = b'{"amount": 500, "currency": "INR"}'
        fixed_ts = 1732000000
        sig1 = compute_hmac_signature(payload, self.secret, fixed_ts)
        sig2 = compute_hmac_signature(payload, self.secret, fixed_ts)

        self.assertEqual(sig1, sig2)

    def test_tampered_payload_changes_signature(self) -> None:
        """1-byte payload change completely alters HMAC output (avalanche effect)."""
        payload_orig = b'{"amount": 100}'
        payload_tamp = b'{"amount": 101}'
        ts = int(time.time())

        sig1 = compute_hmac_signature(payload_orig, self.secret, ts)
        sig2 = compute_hmac_signature(payload_tamp, self.secret, ts)

        self.assertNotEqual(sig1, sig2)

    def test_different_secret_produces_different_signature(self) -> None:
        """Different secrets produce distinct signatures."""
        payload = b'{"action": "sync"}'
        ts = int(time.time())

        sig1 = compute_hmac_signature(payload, "secret-a", ts)
        sig2 = compute_hmac_signature(payload, "secret-b", ts)

        self.assertNotEqual(sig1, sig2)
