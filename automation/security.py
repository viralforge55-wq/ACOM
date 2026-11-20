"""Client-side M2M HMAC-SHA256 signature generation for Python runners and workers."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Dict

DEFAULT_LOCAL_HMAC_SECRET = "acom-m2m-automation-secret-local-phase7-2026"


def compute_hmac_signature(raw_body: bytes, secret: str, timestamp: str | int) -> str:
    """Compute HMAC-SHA256 signature matching API_CONTRACTS.md §5."""
    key = secret.encode("utf-8")
    message = f"{timestamp}.".encode("utf-8") + raw_body
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def generate_hmac_headers(
    raw_body: bytes,
    secret: str = DEFAULT_LOCAL_HMAC_SECRET,
    timestamp: int | None = None,
) -> Dict[str, str]:
    """Generate headers dict containing X-ACOM-Signature and X-ACOM-Timestamp."""
    ts = int(time.time()) if timestamp is None else int(timestamp)
    sig = compute_hmac_signature(raw_body, secret, ts)
    return {
        "X-ACOM-Signature": sig,
        "X-ACOM-Timestamp": str(ts),
    }
