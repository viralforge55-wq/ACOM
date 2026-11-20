"""Affiliate click recording, rate limiting, deduplication, and redirect resolution.

Implements API_CONTRACTS.md §2 and DATA_DICTIONARY.md §3:
- Anonymous session ID only; zero PII persisted (no IP, email, phone, or raw UA in MariaDB).
- Strict input schema validation; rejects unknown/PII fields.
- Rate limits (Redis cache): 60/hour per session hash, 600/hour per IP hash.
- 2-second deduplication for the same (session_id, affiliate_product) using an
  injectable clock (TEST_PLAN.md §7).
- Rejects non-existent, unpublished, or inactive-network products.
- Never creates revenue or accounting entries.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import frappe
from frappe.utils import now_datetime

from acom_core.affiliate_commerce.doctype.affiliate_click.affiliate_click import (
    ALLOWED_UTM_SOURCES,
    MAX_LANDING_PATH_LEN,
    MEDIUM_PATTERN,
    SESSION_ID_PATTERN,
    classify_user_agent,
    sanitize_referrer,
)
from acom_core.affiliate_commerce.doctype.affiliate_network.affiliate_network import SLUG_PATTERN
from acom_core.api.errors import AcomApiError

SESSION_RATE_LIMIT_PER_HOUR = 60
IP_RATE_LIMIT_PER_HOUR = 600
RATE_WINDOW_SECONDS = 3600
DEDUP_WINDOW_SECONDS = 2

# Allowed body keys per API_CONTRACTS.md §2.
# `clicked_at` is accepted and ignored per API_CONTRACTS.md §2 ("Any client-supplied timestamp is ignored").
ALLOWED_CLICK_FIELDS = frozenset(
    {
        "product_slug",
        "session_id",
        "source",
        "medium",
        "referrer",
        "landing_path",
        "clicked_at",
    }
)


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _enforce_rate_limit(
    *,
    bucket: str,
    identifier: str,
    limit: int,
    window_seconds: int = RATE_WINDOW_SECONDS,
) -> None:
    """Increment an ephemeral Redis counter and raise 429 RATE_LIMITED when exceeded."""
    cache = frappe.cache()
    key = f"acom:rl:{bucket}:{_hash_key(identifier)}"
    current = cache.get_value(key)
    count = int(current) if current is not None else 0
    if count >= limit:
        raise AcomApiError(
            "RATE_LIMITED",
            "Too many click requests. Please slow down.",
            status_code=429,
            details={"bucket": bucket, "limit": limit, "window_seconds": window_seconds},
            headers={"Retry-After": str(window_seconds)},
        )
    cache.set_value(key, count + 1, expires_in_sec=window_seconds)


def _validate_click_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AcomApiError("VALIDATION_ERROR", "Request payload must be a JSON object.", status_code=400)

    unknown_fields = sorted(k for k in payload.keys() if k not in ALLOWED_CLICK_FIELDS)
    if unknown_fields:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Unknown or prohibited fields in request payload.",
            status_code=400,
            details={"fields": unknown_fields},
        )

    product_slug = (payload.get("product_slug") or "").strip().lower()
    if not product_slug or not SLUG_PATTERN.match(product_slug):
        raise AcomApiError(
            "VALIDATION_ERROR",
            "product_slug is required and must be a valid slug.",
            status_code=400,
            details={"fields": ["product_slug"]},
        )

    session_id = (payload.get("session_id") or "").strip()
    if not session_id or not SESSION_ID_PATTERN.match(session_id):
        raise AcomApiError(
            "VALIDATION_ERROR",
            "session_id is required and must be 8-128 alphanumeric/hyphen/underscore chars.",
            status_code=400,
            details={"fields": ["session_id"]},
        )

    source = payload.get("source")
    if source is not None and str(source).strip():
        source = str(source).strip().lower()
        if source not in ALLOWED_UTM_SOURCES:
            raise AcomApiError(
                "VALIDATION_ERROR",
                "source is not in the allowed UTM source list.",
                status_code=400,
                details={"fields": ["source"]},
            )
    else:
        source = None

    medium = payload.get("medium")
    if medium is not None and str(medium).strip():
        medium = str(medium).strip().lower()
        if not MEDIUM_PATTERN.match(medium):
            raise AcomApiError(
                "VALIDATION_ERROR",
                "medium must be 1-64 alphanumeric/hyphen/underscore chars.",
                status_code=400,
                details={"fields": ["medium"]},
            )
    else:
        medium = None

    landing_path = payload.get("landing_path")
    if landing_path is not None and str(landing_path).strip():
        landing_path = str(landing_path).strip()
        if not landing_path.startswith("/") or len(landing_path) > MAX_LANDING_PATH_LEN:
            raise AcomApiError(
                "VALIDATION_ERROR",
                "landing_path must be a relative path starting with '/'.",
                status_code=400,
                details={"fields": ["landing_path"]},
            )
    else:
        landing_path = None

    referrer_raw = payload.get("referrer")
    referrer = None
    if referrer_raw is not None and str(referrer_raw).strip():
        try:
            referrer = sanitize_referrer(str(referrer_raw))
        except frappe.ValidationError as exc:
            raise AcomApiError(
                "VALIDATION_ERROR",
                "referrer must be a valid http(s) URL.",
                status_code=400,
                details={"fields": ["referrer"]},
            ) from exc

    return {
        "product_slug": product_slug,
        "session_id": session_id,
        "source": source,
        "medium": medium,
        "landing_path": landing_path,
        "referrer": referrer,
    }


def record_click(
    payload: dict[str, Any],
    *,
    user_agent: str | None = None,
    client_ip: str | None = None,
    now_fn: Callable[[], datetime] = now_datetime,
    enforce_rate_limits: bool = True,
) -> tuple[dict[str, Any], int]:
    """Validate, rate-limit, deduplicate, and persist an Affiliate Click.

    Returns (data_dict, http_status_code).
    """
    cleaned = _validate_click_payload(payload)

    if enforce_rate_limits:
        _enforce_rate_limit(
            bucket="click_session",
            identifier=cleaned["session_id"],
            limit=SESSION_RATE_LIMIT_PER_HOUR,
        )
        if client_ip:
            _enforce_rate_limit(
                bucket="click_ip",
                identifier=client_ip,
                limit=IP_RATE_LIMIT_PER_HOUR,
            )

    product = frappe.db.get_value(
        "Affiliate Product",
        {"slug": cleaned["product_slug"]},
        ["name", "status", "affiliate_network", "campaign"],
        as_dict=True,
    )
    if not product:
        raise AcomApiError(
            "NOT_FOUND",
            "Affiliate product not found.",
            status_code=404,
            details={"product_slug": cleaned["product_slug"]},
        )

    if product["status"] != "Published":
        raise AcomApiError(
            "PRODUCT_UNAVAILABLE",
            "Product is not currently published.",
            status_code=422,
            details={"product_slug": cleaned["product_slug"]},
        )

    network_status = frappe.db.get_value(
        "Affiliate Network", product["affiliate_network"], "status"
    )
    if network_status != "Active":
        raise AcomApiError(
            "PRODUCT_UNAVAILABLE",
            "Affiliate network for this product is not active.",
            status_code=422,
            details={"product_slug": cleaned["product_slug"]},
        )

    # Deduplicate identical (session_id, affiliate_product) clicks within 2 seconds.
    current_time = now_fn()
    cutoff = current_time - timedelta(seconds=DEDUP_WINDOW_SECONDS)
    existing_clicks = frappe.get_all(
        "Affiliate Click",
        filters={
            "session_id": cleaned["session_id"],
            "affiliate_product": product["name"],
            "clicked_at": [">=", cutoff],
        },
        fields=["click_id"],
        order_by="clicked_at desc",
        limit=1,
        ignore_permissions=True,
    )
    if existing_clicks:
        click_id = existing_clicks[0]["click_id"]
        return (
            {"click_id": click_id, "redirect_url": f"/go/{click_id}"},
            200,
        )

    ua_family, is_bot = classify_user_agent(user_agent)

    doc = frappe.get_doc(
        {
            "doctype": "Affiliate Click",
            "affiliate_product": product["name"],
            "session_id": cleaned["session_id"],
            "source": cleaned["source"],
            "medium": cleaned["medium"],
            "referrer": cleaned["referrer"],
            "landing_path": cleaned["landing_path"],
            "user_agent_family": ua_family,
            "is_bot_suspected": is_bot,
        }
    )
    doc.insert(ignore_permissions=True)

    return (
        {
            "click_id": doc.click_id,
            "redirect_url": f"/go/{doc.click_id}",
        },
        201,
    )


def resolve_redirect(click_id: str) -> dict[str, Any]:
    """Resolve a recorded click_id to its outbound affiliate URL with sub-ID parameter."""
    cleaned = (click_id or "").strip()
    try:
        parsed_uuid = uuid.UUID(cleaned, version=4)
        if str(parsed_uuid) != cleaned.lower():
            raise ValueError("not canonical uuid4")
    except ValueError as exc:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "click_id must be a valid UUIDv4.",
            status_code=400,
            details={"fields": ["click_id"]},
        ) from exc

    click = frappe.db.get_value(
        "Affiliate Click",
        cleaned,
        ["click_id", "affiliate_product"],
        as_dict=True,
    )
    if not click:
        raise AcomApiError("NOT_FOUND", "Affiliate click not found.", status_code=404)

    product = frappe.db.get_value(
        "Affiliate Product",
        click["affiliate_product"],
        ["name", "status", "affiliate_network", "affiliate_url"],
        as_dict=True,
    )
    if not product or product["status"] != "Published":
        raise AcomApiError(
            "PRODUCT_UNAVAILABLE",
            "Product is no longer available.",
            status_code=422,
        )

    network_status = frappe.db.get_value(
        "Affiliate Network", product["affiliate_network"], "status"
    )
    if network_status != "Active":
        raise AcomApiError(
            "PRODUCT_UNAVAILABLE",
            "Affiliate network is not active.",
            status_code=422,
        )

    # Append click_id as subid parameter so network reports can match conversions back.
    parsed = urlparse(product["affiliate_url"])
    params = parse_qsl(parsed.query, keep_blank_values=True)
    if not any(k == "subid" for k, _ in params):
        params.append(("subid", click["click_id"]))
    destination = urlunparse(parsed._replace(query=urlencode(params)))

    return {
        "click_id": click["click_id"],
        "destination_url": destination,
        "rel": "sponsored nofollow",
    }
