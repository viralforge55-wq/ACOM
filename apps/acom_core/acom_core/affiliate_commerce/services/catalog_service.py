"""Public read-only catalog service (API_CONTRACTS.md §1, DATA_DICTIONARY.md §13).

Serves both AFFILIATE and DROPSHIP Published products with strict separation:
- Strictly selects explicit safe columns via Frappe ORM (zero raw SQL, never doc.as_dict()).
- Affiliate products return `sales_type: "AFFILIATE"`, `cta_label: "View Deal"`, and NEVER raw `affiliate_url`.
- Dropship products return `sales_type: "DROPSHIP"`, `cta_label: "Add to Cart"`, coarse `availability`
  band (NEVER raw `supplier_stock`), and NEVER `supplier_cost`, `supplier`, `supplier_sku`, or margins.
- Runtime guard (`assert_no_banned_fields`) verifies recursively that no banned field ever leaves.
"""

from __future__ import annotations

import math
from decimal import Decimal
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
# plus private dropshipping cost/stock/ERP fields and Frappe internal metadata.
BANNED_PUBLIC_FIELDS = frozenset(
    {
        "supplier_cost",
        "supplier",
        "supplier_sku",
        "supplier_stock",
        "shipping_cost",
        "packaging_cost",
        "price_list",
        "erpnext_item",
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


def _quantity_band(raw_stock: int | None) -> tuple[bool, str]:
    qty = int(raw_stock or 0)
    if qty >= 5:
        return (True, "5+")
    if qty > 0:
        return (True, "1-4")
    return (False, "Out of Stock")


def _serialize_affiliate_card(row: dict[str, Any]) -> dict[str, Any]:
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


def _serialize_dropship_card(row: dict[str, Any]) -> dict[str, Any]:
    category_name = row.get("category") or ""
    in_stock, band = _quantity_band(row.get("supplier_stock"))
    price_obj = format_money(row["selling_price"], row.get("currency") or "INR")
    item: dict[str, Any] = {
        "id": row["name"],
        "slug": row["slug"],
        "title": row["product_name"],
        "sales_type": "DROPSHIP",
        "category": {
            "slug": normalize_slug(category_name),
            "name": category_name,
        },
        "marketplace": "ACOM Direct",
        "display_price": price_obj,
        "price": price_obj,
        "availability": {
            "in_stock": in_stock,
            "quantity_band": band,
            "ships_in_days": int(row.get("lead_time_days") or 3),
        },
        "cta_label": "Add to Cart",
    }
    if row.get("image"):
        item["image_url"] = row["image"]
    return item


def _resolve_category_filter(category_param: str) -> str | None:
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


def _sort_key_for_merged(entry: tuple[dict[str, Any], str, Decimal], sort: str):
    card, ts, price_dec = entry
    if sort == "price_asc":
        return (price_dec, card["slug"])
    if sort == "price_desc":
        return (-price_dec, card["slug"])
    return ts


def list_public_catalog(
    *,
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    sales_type: str | None = None,
    sort: str = "newest",
    q: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return paginated public catalog items (AFFILIATE and/or DROPSHIP) and metadata."""
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

    resolved_cat: str | None = None
    if category is not None and str(category).strip():
        resolved_cat = _resolve_category_filter(str(category))
        if not resolved_cat:
            return (
                {"items": []},
                {"total": 0, "page": page_num, "page_size": size_num, "has_next": False},
            )

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

    merged: list[tuple[dict[str, Any], str, Decimal]] = []

    # 1. Affiliate Products
    if normalized_sales_type in (None, "AFFILIATE"):
        active_networks = _active_network_names()
        if active_networks:
            aff_filters: dict[str, Any] = {
                "status": "Published",
                "affiliate_network": ["in", active_networks],
            }
            if resolved_cat:
                aff_filters["category"] = resolved_cat

            aff_rows = frappe.get_all(
                "Affiliate Product",
                filters=aff_filters,
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
                    "creation",
                    "modified",
                ],
                ignore_permissions=True,
            )
            for row in aff_rows:
                card = _serialize_affiliate_card(row)
                ts = str(row.get("modified") if normalized_sort == "popular" else row.get("creation") or "")
                price_dec = (
                    Decimal(str(row["display_price"]))
                    if row.get("display_price") is not None
                    else Decimal("0")
                )
                merged.append((card, ts, price_dec))

    # 2. Dropshipping Products
    if normalized_sales_type in (None, "DROPSHIP") and frappe.db.table_exists("Dropshipping Product"):
        ds_filters: dict[str, Any] = {"status": "Published"}
        if resolved_cat:
            ds_filters["category"] = resolved_cat

        ds_rows = frappe.get_all(
            "Dropshipping Product",
            filters=ds_filters,
            or_filters=or_filters,
            fields=[
                "name",
                "slug",
                "product_name",
                "category",
                "image",
                "selling_price",
                "currency",
                "supplier_stock",
                "lead_time_days",
                "creation",
                "modified",
            ],
            ignore_permissions=True,
        )
        for row in ds_rows:
            card = _serialize_dropship_card(row)
            ts = str(row.get("modified") if normalized_sort == "popular" else row.get("creation") or "")
            price_dec = Decimal(str(row.get("selling_price") or 0))
            merged.append((card, ts, price_dec))

    reverse_sort = normalized_sort in ("newest", "popular")
    merged.sort(key=lambda e: _sort_key_for_merged(e, normalized_sort), reverse=reverse_sort)

    total = len(merged)
    start = (page_num - 1) * size_num
    items = [entry[0] for entry in merged[start : start + size_num]]

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
    """Return full public record for a single Published affiliate or dropship product."""
    cleaned = (slug or "").strip().lower()
    if not cleaned or not SLUG_PATTERN.match(cleaned):
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Invalid product slug format.",
            status_code=400,
            details={"fields": ["slug"]},
        )

    # 1. Try Affiliate Product (Published + Active network)
    active_networks = _active_network_names()
    if active_networks:
        aff_rows = frappe.get_all(
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
        if aff_rows:
            row = aff_rows[0]
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

    # 2. Try Dropshipping Product (Published only; zero supplier cost/identity/raw stock leaked!)
    if frappe.db.table_exists("Dropshipping Product"):
        ds_rows = frappe.get_all(
            "Dropshipping Product",
            filters={"slug": cleaned, "status": "Published"},
            fields=[
                "name",
                "slug",
                "product_name",
                "category",
                "selling_price",
                "currency",
                "supplier_stock",
                "lead_time_days",
                "hsn_code",
                "return_policy_summary",
                "image",
                "short_description",
            ],
            limit=1,
            ignore_permissions=True,
        )
        if ds_rows:
            row = ds_rows[0]
            in_stock, band = _quantity_band(row.get("supplier_stock"))
            category_name = row.get("category") or ""
            ds_product: dict[str, Any] = {
                "id": row["name"],
                "slug": row["slug"],
                "title": row["product_name"],
                "sales_type": "DROPSHIP",
                "category": {
                    "slug": normalize_slug(category_name),
                    "name": category_name,
                },
                "price": format_money(row["selling_price"], row.get("currency") or "INR"),
                "availability": {
                    "in_stock": in_stock,
                    "quantity_band": band,
                    "ships_in_days": int(row.get("lead_time_days") or 3),
                },
                "hsn_category": row.get("hsn_code") or "",
                "return_policy_summary": row.get("return_policy_summary") or "7-day replacement on damage",
                "cta_label": "Add to Cart",
            }
            if row.get("image"):
                ds_product["image_url"] = row["image"]
            if row.get("short_description"):
                ds_product["short_description"] = row["short_description"]

            assert_no_banned_fields(ds_product)
            return ds_product

    raise AcomApiError("NOT_FOUND", "Product not found.", status_code=404)


def list_public_categories() -> dict[str, Any]:
    """Return flat category list with published product counts across AFFILIATE + DROPSHIP."""
    counts: dict[str, int] = {}

    active_networks = _active_network_names()
    if active_networks:
        aff_rows = frappe.get_all(
            "Affiliate Product",
            filters={
                "status": "Published",
                "affiliate_network": ["in", active_networks],
            },
            fields=["category"],
            ignore_permissions=True,
        )
        for row in aff_rows:
            cat = row.get("category")
            if cat:
                counts[cat] = counts.get(cat, 0) + 1

    if frappe.db.table_exists("Dropshipping Product"):
        ds_rows = frappe.get_all(
            "Dropshipping Product",
            filters={"status": "Published"},
            fields=["category"],
            ignore_permissions=True,
        )
        for row in ds_rows:
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
