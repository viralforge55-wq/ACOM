"""ACOM Core — Local-First Ollama Model Abstraction Client.

Enforces ADR-0004 AI model ceiling:
- Windows host Ollama at http://127.0.0.1:11434 (never exposed publicly).
- AI_MAX_CONCURRENT_TASKS = 1 strictly enforced via Semaphore.
- Default resident model: qwen2.5:3b.
- Strict request timeouts and exponential backoff retry policy.
- Output schema validation using Pydantic / JSON schema.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from typing import Any, Callable, Dict, Optional, Type, TypeVar
import requests
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("acom.ai.client")

T = TypeVar("T", bound=BaseModel)

DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("ACOM_AI_DEFAULT_MODEL", "qwen2.5:3b")
MAX_CONCURRENT_TASKS = int(os.environ.get("AI_MAX_CONCURRENT_TASKS", "1"))

# Process-level semaphore enforcing AI_MAX_CONCURRENT_TASKS = 1 (ADR-0004)
_CONCURRENCY_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT_TASKS)


class AIClientError(Exception):
    """Base exception for AI client failures."""
    pass


class OllamaOfflineError(AIClientError):
    """Raised when Ollama host is unreachable or down."""
    pass


class OllamaTimeoutError(AIClientError):
    """Raised when inference exceeds declared execution timeout."""
    pass


class SchemaValidationError(AIClientError):
    """Raised when model output fails JSON parsing or Pydantic validation."""
    pass


def _extract_json_from_text(text: str) -> dict[str, Any]:
    """Extract JSON object from raw model completion text."""
    text = text.strip()
    if text.startswith("```"):
        # Strip markdown fences
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
        text = text.strip()

    # Find the outermost { ... }
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        text = text[start_idx : end_idx + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(f"Invalid JSON in model output: {str(exc)}") from exc


class OllamaClient:
    """Thread-safe client for local Ollama instance with concurrency gating."""

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_HOST,
        default_model: str = DEFAULT_MODEL,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        mock_handler: Optional[Callable[[str, str], str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.mock_handler = mock_handler

    def is_healthy(self) -> bool:
        """Check if local Ollama daemon is running and reachable."""
        if self.mock_handler:
            return True
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        schema_model: Optional[Type[T]] = None,
        timeout: Optional[float] = None,
    ) -> tuple[dict[str, Any], int, int]:
        """Execute inference with strict concurrency, timeout, and schema validation.

        Returns (cleaned_dict, prompt_tokens, completion_tokens).
        """
        target_model = model or self.default_model
        req_timeout = timeout or self.timeout_seconds

        # Acquire concurrency gate (strictly 1 at a time per ADR-0004)
        acquired = _CONCURRENCY_SEMAPHORE.acquire(timeout=req_timeout)
        if not acquired:
            raise OllamaTimeoutError(
                f"Timed out waiting for AI concurrency slot ({MAX_CONCURRENT_TASKS} max concurrent)"
            )

        try:
            return self._execute_with_retry(
                prompt=prompt,
                system_prompt=system_prompt,
                model=target_model,
                schema_model=schema_model,
                timeout=req_timeout,
            )
        finally:
            _CONCURRENCY_SEMAPHORE.release()

    def _execute_with_retry(
        self,
        prompt: str,
        system_prompt: str,
        model: str,
        schema_model: Optional[Type[T]],
        timeout: float,
    ) -> tuple[dict[str, Any], int, int]:
        """Execute request with exponential backoff on transient errors."""
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                raw_text, prompt_tokens, completion_tokens = self._call_ollama_raw(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model=model,
                    timeout=timeout,
                )

                # Parse JSON
                parsed_json = _extract_json_from_text(raw_text)

                # Validate with Pydantic if schema model is provided
                if schema_model:
                    try:
                        validated_obj = schema_model.model_validate(parsed_json)
                        parsed_json = validated_obj.model_dump(mode="json")
                    except ValidationError as ve:
                        raise SchemaValidationError(
                            f"Pydantic schema validation failed: {str(ve)}"
                        ) from ve

                return parsed_json, prompt_tokens, completion_tokens

            except (requests.exceptions.ConnectionError, OllamaOfflineError) as conn_err:
                last_error = OllamaOfflineError(
                    f"Ollama server unreachable at {self.base_url}: {str(conn_err)}"
                )
                if attempt < self.max_retries:
                    time.sleep(1.0 * (2 ** attempt))
                    continue
                raise last_error

            except (requests.exceptions.Timeout, OllamaTimeoutError) as to_err:
                last_error = OllamaTimeoutError(
                    f"Inference request timed out after {timeout}s: {str(to_err)}"
                )
                if attempt < self.max_retries:
                    time.sleep(1.0 * (2 ** attempt))
                    continue
                raise last_error

            except SchemaValidationError as sve:
                # Schema validation errors are not retried against the model blindly
                raise sve

            except Exception as exc:
                last_error = AIClientError(f"Unexpected inference error: {str(exc)}")
                if attempt < self.max_retries:
                    time.sleep(1.0 * (2 ** attempt))
                    continue
                raise last_error

        if last_error:
            raise last_error
        raise AIClientError("Failed to generate response after retries")

    def _call_ollama_raw(
        self,
        prompt: str,
        system_prompt: str,
        model: str,
        timeout: float,
    ) -> tuple[str, int, int]:
        """Perform raw HTTP call to Ollama or mock handler."""
        if self.mock_handler:
            raw_output = self.mock_handler(prompt, system_prompt)
            return raw_output, 100, 150

        endpoint = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
            },
        }

        resp = requests.post(endpoint, json=payload, timeout=timeout)
        if resp.status_code != 200:
            raise AIClientError(
                f"Ollama API returned HTTP {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()
        message = data.get("message", {}).get("content", "")
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        return message, prompt_tokens, completion_tokens
