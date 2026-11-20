"""Host-side Python automation worker / runner (ADR-0002).

Coordinates local AI inference (via host Ollama) and ERPNext synchronization
via HMAC-authenticated internal endpoints.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict

from automation.security import generate_hmac_headers

DEFAULT_ERPNEXT_URL = os.environ.get("ACOM_ERPNEXT_URL", "http://127.0.0.1:8080")
DEFAULT_HOST_HEADER = os.environ.get("ACOM_SITE_HOST", "acom.localhost")
DEFAULT_SECRET = os.environ.get("ACOM_AUTOMATION_HMAC_SECRET", "acom-m2m-automation-secret-local-phase7-2026")


class AutomationRunner:
    """Dispatches workflow jobs and synchronizes with ERPNext via HMAC M2M."""

    def __init__(
        self,
        base_url: str = DEFAULT_ERPNEXT_URL,
        site_host: str = DEFAULT_HOST_HEADER,
        hmac_secret: str = DEFAULT_SECRET,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.site_host = site_host
        self.hmac_secret = hmac_secret

    def _call_m2m_endpoint(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make an HMAC-signed POST request to an ERPNext endpoint."""
        url = f"{self.base_url}/api/method/{endpoint.lstrip('/')}"
        raw_body = json.dumps(payload).encode("utf-8")
        headers = generate_hmac_headers(raw_body, secret=self.hmac_secret)
        headers["Host"] = self.site_host
        headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=raw_body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read().decode("utf-8")
                parsed = json.loads(data)
                if isinstance(parsed, dict) and "message" in parsed and isinstance(parsed["message"], dict):
                    return parsed["message"]
                return parsed
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(err_body)
                if isinstance(parsed, dict) and "message" in parsed and isinstance(parsed["message"], dict):
                    res = parsed["message"]
                    res["status_code"] = exc.code
                    return res
                parsed["status_code"] = exc.code
                return parsed
            except Exception:
                return {
                    "ok": False,
                    "error": {"code": f"HTTP_{exc.code}", "message": err_body},
                    "status_code": exc.code,
                }
        except Exception as exc:
            return {"ok": False, "error": {"code": "CONNECTION_ERROR", "message": str(exc)}}

    def inject_event(
        self,
        event_type: str,
        idempotency_key: str,
        payload: Dict[str, Any],
        source: str = "Agent",
    ) -> Dict[str, Any]:
        """Inject an event into the ERPNext Automation Event outbox."""
        return self._call_m2m_endpoint(
            "acom_core.api.automation.inject_event",
            {
                "event_type": event_type,
                "idempotency_key": idempotency_key,
                "payload": payload,
                "source": source,
            },
        )

    def trigger_workflow(self, workflow_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger an automation workflow inside ERPNext."""
        return self._call_m2m_endpoint(
            "acom_core.api.automation.trigger_workflow",
            {
                "workflow": workflow_name,
                "parameters": params,
            },
        )

    def get_event_status(self, event_id: str | None = None, idempotency_key: str | None = None) -> Dict[str, Any]:
        """Query event processing status."""
        return self._call_m2m_endpoint(
            "acom_core.api.automation.get_event_status",
            {
                "event_id": event_id,
                "idempotency_key": idempotency_key,
            },
        )
