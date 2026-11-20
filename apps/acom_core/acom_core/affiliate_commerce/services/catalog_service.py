"""Public read-only catalog service (API_CONTRACTS.md §1, DATA_DICTIONARY.md §13).

Security invariants:
- Strictly selects explicit safe columns via Frappe ORM (zero raw SQL, never doc.as_dict()).
- Only returns Affiliate Products where status == 'Published' AND linked
  Affiliate Network status == 'Active'.
- Runtime guard (`assert_no_banned_fields`) verifies recursively that no banned
  or private field ever leaves this service.
"""

from __future__ import annotations

import math
from typing import Any

import frappe

from acom_core.affiliate_commerce.doctype.affiliate_network.affiliate_network import (
    SLUG_PATTERN,
    normalize_slug,
)
from acom_core.api.errors import AcomApiError, format_money

DEFAULT_DISCLOSURE_TEXT = (
    "As an affiliate partner, we may earn a commission from qualifying "
    "purchases made through links on this page, at no extra cost to you."
)

ALLOWED_SALES_TYPES = frozenset({"AFFILIATE", "DROPSHIP"})
ALLOWED_SORTS = frozenset({"newest", "popular", "price_asc", "price_desc"})
MAX_PAGE_SIZE = 100

# Authoritative union of DATA_DICTIONARY.md §13 + API_CONTRACTS.md §1 forbidden fields
# plus Frappe internal document metadata that must never leak on public endpoints.
BANNED_PUBLIC_FIELDS = frozenset(
    {
        "supplier_cost",
        "supplier",
        "supplier_sku",
        "contribution_profit",
        "contribution_margin_pct",
        "payment_fee_percent",
        "expected_return_rate",
        "commission_rate",
        "commission_type",
        "commission_flat_amount",
        "commission_amount",
        "commission_status",
        "network_conversion_id",
        "affiliate_url",
        "affiliate_network",
        "payload",
        "error_details",
        "owner",
        "modified_by",
        "creation",
        "modified",
        "docstatus",
        "idx",
        "ai_task",
        "approval_status",
        "approved_by",
        "decision_note",
        "rationale",
        "recommendation",
        "risk_level",
        "verification_method",
        "last_verified_date",
        "content_review_status",
    }
)


def assert_no_banned_fields(obj: Any, path: str = "$") -> None:
    """Recursively verify that no banned or private field appears in a public payload."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in BANNED_PUBLIC_FIELDS:
                frappe.log_error(
                    title="ACOM security guard blocked banned public field",
                    message=f"Blocked banned key '{key}' at {path}",
                )
                raise AcomApiError(
                    "INTERNAL_ERROR",
                    "Internal catalog serialization error.",
                    status_code=500,
                )
            assert_no_banned_fields(value, f"{path}.{key}")
    elif isinstance(obj, (list, tuple)):
        for idx, item in enumerate(obj):
            assert_no_banned_fields(item, f"{path}[{idx}]")


def _active_network_names() -> list[str]:
    return frappe.get_all(
        "Affiliate Network",
        filters={"status": "Active"},
        pluck="name",
        ignore_permissions=True,
    )


def _get_disclosure_text() -> str:
    try:
        text = frappe.db.get_single_value("ACOM Settings", "affiliate_disclosure_text")
        if text and str(text).strip():
            return str(text).strip()
    except Exception:
        pass
    return DEFAULT_DISCLOSURE_TEXT


def _serialize_catalog_card(row: dict[str, Any]) -> dict[str, Any]:
    category_name = row.get("category") or ""
    item: dict[str, Any] = {
        "id": row["name"],
        "slug": row["slug"],
        "title": row["product_name"],
        "sales_type": "AFFILIATE",
        "category": {
            "slug": normalize_slug(category_name),
            "name": category_name,
        },
        "marketplace": row["marketplace"],
        "cta_label": "View Deal",
    }
    if row.get("image"):
        item["image_url"] = row["image"]
    if row.get("display_price") is not None:
        item["display_price"] = format_money(row["display_price"], row.get("currency") or "INR")
    return item


def _resolve_category_filter(category_param: str) -> str | None:
    """Resolve category query param (either exact Item Group name or normalized slug)."""
    cleaned = category_param.strip()
    if not cleaned:
        return None
    if frappe.db.exists("Item Group", cleaned):
        return cleaned
    target_slug = cleaned.lower()
    groups = frappe.get_all("Item Group", pluck="name", ignore_permissions=True)
    for name in groups:
        if normalize_slug(name) == target_slug:
            return name
    return None


def list_public_catalog(
    *,
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    sales_type: str | None = None,
    sort: str = "newest",
    q: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return paginated public catalog items and pagination metadata."""
    try:
        page_num = int(page)
        size_num = int(page_size)
    except (TypeError, ValueError) as exc:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "page and page_size must be integers.",
            status_code=400,
            details={"fields": ["page", "page_size"]},
        ) from exc

    if page_num < 1:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "page must be >= 1.",
            status_code=400,
            details={"fields": ["page"]},
        )
    if size_num < 1 or size_num > MAX_PAGE_SIZE:
        raise AcomApiError(
            "VALIDATION_ERROR",
            f"page_size must be between 1 and {MAX_PAGE_SIZE}.",
            status_code=400,
            details={"fields": ["page_size"]},
        )

    normalized_sales_type = None
    if sales_type is not None and str(sales_type).strip():
        normalized_sales_type = str(sales_type).strip().upper()
        if normalized_sales_type not in ALLOWED_SALES_TYPES:
            raise AcomApiError(
                "VALIDATION_ERROR",
                "sales_type must be AFFILIATE or DROPSHIP.",
                status_code=400,
                details={"fields": ["sales_type"]},
            )

    normalized_sort = (sort or "newest").strip().lower()
    if normalized_sort not in ALLOWED_SORTS:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "sort must be one of newest, popular, price_asc, price_desc.",
            status_code=400,
            details={"fields": ["sort"]},
        )

    # Phase 2 is Affiliate-only (ADR-0001); DROPSHIP cleanly returns an empty catalog.
    if normalized_sales_type == "DROPSHIP":
        return (
            {"items": []},
            {"total": 0, "page": page_num, "page_size": size_num, "has_next": False},
        )

    active_networks = _active_network_names()
    if not active_networks:
        return (
            {"items": []},
            {"total": 0, "page": page_num, "page_size": size_num, "has_next": False},
        )

    filters: dict[str, Any] = {
        "status": "Published",
        "affiliate_network": ["in", active_networks],
    }

    if category is not None and str(category).strip():
        resolved_cat = _resolve_category_filter(str(category))
        if not resolved_cat:
            return (
                {"items": []},
                {"total": 0, "page": page_num, "page_size": size_num, "has_next": False},
            )
        filters["category"] = resolved_cat

    or_filters = None
    if q is not None and str(q).strip():
        query = str(q).strip()
        if len(query) > 120:
            raise AcomApiError(
                "VALIDATION_ERROR",
                "q must be at most 120 characters.",
                status_code=400,
                details={"fields": ["q"]},
            )
        or_filters = {
            "product_name": ["like", f"%{query}%"],
            "short_description": ["like", f"%{query}%"],
        }

    order_map = {
        "newest": "creation desc",
        "popular": "modified desc",
        "price_asc": "display_price asc, creation desc",
        "price_desc": "display_price desc, creation desc",
    }

    all_matching_names = frappe.get_all(
        "Affiliate Product",
        filters=filters,
        or_filters=or_filters,
        pluck="name",
        ignore_permissions=True,
    )
    total = len(all_matching_names)

    start = (page_num - 1) * size_num
    rows = frappe.get_all(
        "Affiliate Product",
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name",
            "slug",
            "product_name",
            "category",
            "image",
            "display_price",
            "currency",
            "marketplace",
        ],
        order_by=order_map[normalized_sort],
        start=start,
        limit=size_num,
        ignore_permissions=True,
    )

    items = [_serialize_catalog_card(row) for row in rows]
    data = {"items": items}
    assert_no_banned_fields(data)

    total_pages = math.ceil(total / size_num) if total > 0 else 0
    meta = {
        "total": total,
        "page": page_num,
        "page_size": size_num,
        "has_next": page_num < total_pages,
    }
    return data, meta


def get_public_product_by_slug(slug: str) -> dict[str, Any]:
    """Return full public record for a single Published affiliate product.

    Never reveals raw `affiliate_url`, commission fields, or unpublished products.
    """
    cleaned = (slug or "").strip().lower()
    if not cleaned or not SLUG_PATTERN.match(cleaned):
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Invalid product slug format.",
            status_code=400,
            details={"fields": ["slug"]},
        )

    active_networks = _active_network_names()
    if not active_networks:
        raise AcomApiError("NOT_FOUND", "Product not found.", status_code=404)

    rows = frappe.get_all(
        "Affiliate Product",
        filters={
            "slug": cleaned,
            "status": "Published",
            "affiliate_network": ["in", active_networks],
        },
        fields=[
            "name",
            "slug",
            "product_name",
            "product_sku",
            "category",
            "marketplace",
            "display_price",
            "currency",
            "image",
            "short_description",
            "long_description",
            "seo_title",
            "seo_description",
            "disclosure_required",
        ],
        limit=1,
        ignore_permissions=True,
    )
    if not rows:
        raise AcomApiError("NOT_FOUND", "Product not found.", status_code=404)

    row = rows[0]
    highlights = frappe.get_all(
        "Product Highlight",
        filters={"parent": row["name"], "parenttype": "Affiliate Product"},
        fields=["parentfield", "text", "sort_order"],
        order_by="sort_order asc, idx asc",
        ignore_permissions=True,
    )
    pros = [h["text"] for h in highlights if h["parentfield"] == "pros"]
    cons = [h["text"] for h in highlights if h["parentfield"] == "cons"]

    category_name = row.get("category") or ""
    product: dict[str, Any] = {
        "id": row["name"],
        "slug": row["slug"],
        "title": row["product_name"],
        "product_sku": row["product_sku"],
        "sales_type": "AFFILIATE",
        "category": {
            "slug": normalize_slug(category_name),
            "name": category_name,
        },
        "marketplace": row["marketplace"],
        "cta_label": "View Deal",
        "disclosure_required": bool(row.get("disclosure_required", 1)),
        "affiliate_disclosure": _get_disclosure_text(),
        # Server-side redirector workflow; raw affiliate_url is NEVER returned here.
        "view_deal_url": "/api/affiliate/click",
        "pros": pros,
        "cons": cons,
    }
    if row.get("image"):
        product["image_url"] = row["image"]
    if row.get("display_price") is not None:
        product["display_price"] = format_money(row["display_price"], row.get("currency") or "INR")
    if row.get("short_description"):
        product["short_description"] = row["short_description"]
    if row.get("long_description"):
        product["long_description"] = row["long_description"]
    if row.get("seo_title"):
        product["seo_title"] = row["seo_title"]
    if row.get("seo_description"):
        product["seo_description"] = row["seo_description"]

    assert_no_banned_fields(product)
    return product


def list_public_categories() -> dict[str, Any]:
    """Return flat category list with published product counts (API_CONTRACTS.md §1)."""
    active_networks = _active_network_names()
    if not active_networks:
        return {"categories": []}

    rows = frappe.get_all(
        "Affiliate Product",
        filters={
            "status": "Published",
            "affiliate_network": ["in", active_networks],
        },
        fields=["category"],
        ignore_permissions=True,
    )
    counts: dict[str, int] = {}
    for row in rows:
        cat = row.get("category")
        if cat:
            counts[cat] = counts.get(cat, 0) + 1

    if not counts:
        return {"categories": []}

    item_groups = frappe.get_all(
        "Item Group",
        filters={"name": ["in", list(counts.keys())]},
        fields=["name", "parent_item_group"],
        order_by="name asc",
        ignore_permissions=True,
    )

    categories = [
        {
            "slug": normalize_slug(grp["name"]),
            "name": grp["name"],
            "product_count": counts.get(grp["name"], 0),
            "parent": grp.get("parent_item_group") or None,
        }
        for grp in item_groups
    ]
    data = {"categories": categories}
    assert_no_banned_fields(data)
    return data
