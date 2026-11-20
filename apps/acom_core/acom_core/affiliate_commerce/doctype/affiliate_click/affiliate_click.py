"""Controller for Affiliate Click DocType (DATA_DICTIONARY.md §3).

Append-only telemetry with zero PII:
- `click_id` is always a server-generated UUIDv4.
- `clicked_at` is always server time (`now_datetime()`), never client-supplied.
- Immutable after insert (only `attribution_status` and `is_bot_suspected` may change).
- Deletion blocked except during explicit retention purge or automated tests.
- Never stores IP addresses, emails, phone numbers, or full User-Agent strings.
"""

from __future__ import annotations

import re
import uuid
from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
MEDIUM_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_REFERRER_LEN = 512
MAX_LANDING_PATH_LEN = 512

ALLOWED_UTM_SOURCES = frozenset(
    {
        "direct",
        "google",
        "bing",
        "duckduckgo",
        "youtube",
        "instagram",
        "facebook",
        "twitter",
        "x",
        "reddit",
        "whatsapp",
        "telegram",
        "email",
        "newsletter",
        "referral",
        "organic",
        "internal",
        "other",
    }
)

ALLOWED_UA_FAMILIES = frozenset(
    {
        "Chrome",
        "Safari",
        "Firefox",
        "Edge",
        "Opera",
        "Bot",
        "Other",
    }
)

IMMUTABLE_FIELDS = (
    "click_id",
    "affiliate_product",
    "campaign_id",
    "source",
    "medium",
    "referrer",
    "landing_path",
    "session_id",
    "clicked_at",
    "user_agent_family",
)


def sanitize_referrer(raw_referrer: str | None) -> str | None:
    """Validate and truncate referrer per DATA_DICTIONARY.md §3.

    If the referrer exceeds 512 chars, store host only. Non-http(s) schemes are rejected.
    """
    if not raw_referrer:
        return None
    cleaned = raw_referrer.strip()
    if not cleaned:
        return None

    parsed = urlparse(cleaned)
    if (parsed.scheme or "").lower() not in {"http", "https"} or not parsed.netloc:
        frappe.throw(_("Referrer must be a valid http(s) URL."), frappe.ValidationError)

    if len(cleaned) > MAX_REFERRER_LEN:
        return parsed.netloc[:MAX_REFERRER_LEN]
    return cleaned


def classify_user_agent(raw_ua: str | None) -> tuple[str, int]:
    """Map raw User-Agent header to a coarse family and bot flag.

    The raw User-Agent string is never persisted.
    """
    if not raw_ua:
        return ("Other", 0)
    ua = raw_ua.lower()
    bot_tokens = (
        "bot",
        "crawl",
        "spider",
        "slurp",
        "headless",
        "scraper",
        "curl/",
        "wget/",
        "python-requests",
        "httpclient",
        "ahrefs",
        "semrush",
    )
    if any(token in ua for token in bot_tokens):
        return ("Bot", 1)
    if "edg/" in ua or "edge/" in ua:
        return ("Edge", 0)
    if "opr/" in ua or "opera" in ua:
        return ("Opera", 0)
    if "firefox/" in ua:
        return ("Firefox", 0)
    if "chrome/" in ua or "crios/" in ua:
        return ("Chrome", 0)
    if "safari/" in ua:
        return ("Safari", 0)
    return ("Other", 0)


class AffiliateClick(Document):
    def before_insert(self) -> None:
        # Always generate server-side UUIDv4 and server timestamp.
        self.click_id = str(uuid.uuid4())
        self.clicked_at = now_datetime()
        self.attribution_status = "Recorded"

        if self.affiliate_product:
            campaign = frappe.db.get_value(
                "Affiliate Product", self.affiliate_product, "campaign"
            )
            self.campaign_id = campaign or None

    def before_validate(self) -> None:
        if self.session_id:
            self.session_id = self.session_id.strip()
        if self.source:
            self.source = self.source.strip().lower()
        if self.medium:
            self.medium = self.medium.strip().lower()
        if self.landing_path:
            self.landing_path = self.landing_path.strip()
        if self.referrer:
            self.referrer = sanitize_referrer(self.referrer)
        if not self.user_agent_family:
            self.user_agent_family = "Other"

    def validate(self) -> None:
        if not self.session_id or not SESSION_ID_PATTERN.match(self.session_id):
            frappe.throw(
                _(
                    "Session ID must be 8-128 characters containing only "
                    "letters, digits, underscores, or hyphens."
                ),
                frappe.ValidationError,
            )

        if self.source and self.source not in ALLOWED_UTM_SOURCES:
            frappe.throw(
                _("Source '{0}' is not in the allowed UTM source list.").format(self.source),
                frappe.ValidationError,
            )

        if self.medium and not MEDIUM_PATTERN.match(self.medium):
            frappe.throw(
                _("Medium must be 1-64 characters (letters, digits, hyphens, underscores)."),
                frappe.ValidationError,
            )

        if self.landing_path:
            if not self.landing_path.startswith("/") or len(self.landing_path) > MAX_LANDING_PATH_LEN:
                frappe.throw(
                    _("Landing Path must be a relative path starting with '/' (max {0} chars).").format(
                        MAX_LANDING_PATH_LEN
                    ),
                    frappe.ValidationError,
                )

        if self.user_agent_family not in ALLOWED_UA_FAMILIES:
            frappe.throw(
                _("User Agent Family must be a coarse allowed family, never a raw UA string."),
                frappe.ValidationError,
            )

        if not self.is_new():
            self._enforce_immutability()

    def _enforce_immutability(self) -> None:
        existing = frappe.db.get_value(
            "Affiliate Click", self.name, IMMUTABLE_FIELDS, as_dict=True
        )
        if not existing:
            return
        for fieldname in IMMUTABLE_FIELDS:
            old_val = existing.get(fieldname)
            new_val = self.get(fieldname)
            if str(old_val or "") != str(new_val or ""):
                frappe.throw(
                    _("Affiliate Click is immutable; field '{0}' cannot be modified.").format(
                        fieldname
                    ),
                    frappe.ValidationError,
                )

    def on_trash(self) -> None:
        if not (frappe.flags.in_test or frappe.flags.get("acom_retention_purge")):
            frappe.throw(
                _("Affiliate Click records are append-only and cannot be deleted manually."),
                frappe.ValidationError,
            )
