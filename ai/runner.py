"""ACOM Core — Controlled AI Task Runner (MASTER_BLUEPRINT §10.2, ADR-0002).

Executes assigned AI tasks against local Ollama models, enforces concurrency
caps and schemas, and securely posts draft outputs to acom_core.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ai.client import (
    OllamaClient,
    OllamaOfflineError,
    OllamaTimeoutError,
    SchemaValidationError,
)
from ai.agents.product_hunter import ProductHunterAgent
from ai.agents.listing_content import ListingContentAgent

logger = logging.getLogger("acom.ai.runner")


class AIRunner:
    """Orchestrates agent execution for AI Tasks."""

    def __init__(self, client: Optional[OllamaClient] = None) -> None:
        self.client = client or OllamaClient()
        self.agents = {
            "product_hunter": ProductHunterAgent(self.client),
            "listing_content": ListingContentAgent(self.client),
        }

    def execute_task(self, agent_id: str, input_payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a single task with an agent."""
        if agent_id not in self.agents:
            return {
                "ok": False,
                "error_code": "UNKNOWN_AGENT",
                "message": f"Agent '{agent_id}' is not registered in runner.",
            }

        agent = self.agents[agent_id]

        try:
            result = agent.run(input_payload)
            return {
                "ok": True,
                "status": "Succeeded",
                "result": result,
            }
        except OllamaOfflineError as off_err:
            logger.warning(f"Ollama is offline: {off_err}")
            return {
                "ok": False,
                "error_code": "OLLAMA_OFFLINE",
                "message": str(off_err),
                "retryable": True,
            }
        except OllamaTimeoutError as to_err:
            logger.warning(f"Ollama inference timed out: {to_err}")
            return {
                "ok": False,
                "error_code": "TIMED_OUT",
                "message": str(to_err),
                "retryable": True,
            }
        except SchemaValidationError as sv_err:
            logger.error(f"Schema validation failure: {sv_err}")
            return {
                "ok": False,
                "error_code": "SCHEMA_INVALID",
                "message": str(sv_err),
                "retryable": False,
            }
        except Exception as exc:
            logger.exception(f"Unexpected agent error: {exc}")
            return {
                "ok": False,
                "error_code": "AGENT_ERROR",
                "message": str(exc),
                "retryable": False,
            }
