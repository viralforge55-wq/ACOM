"""Idempotent Affiliate Conversion Report Import service (DATA_DICTIONARY.md §4, W3–W4).

Invariants:
- Pure Frappe ORM only (zero raw SQL, zero manual frappe.db.commit()).
- Explicit role enforcement: System Manager or ACOM Finance only.
- Atomic pre-validation: schema/column mismatch or invalid/negative amounts reject
  the entire import before any conversion rows are written.
- Idempotent on `(affiliate_network, network_conversion_id)` via DB-enforced
  `dedupe_key` unique index.
- Re-importing unchanged rows skips them; valid status upgrades update cleanly
  with a `status_history` audit entry; reversals create a NEW row and preserve
  the original row untouched.
- Matches conversions to recorded `Affiliate Click` via `subid` / `click_id`,
  respecting `Affiliate Network.cookie_window_days`. Orphan sub-IDs are queued
  (`matched_by = Unmatched`, `needs_manual_review = 1`) rather than dropped.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

import frappe
from frappe.utils import date_diff, getdate

from acom_core.affiliate_commerce.doctype.affiliate_conversion.affiliate_conversion import (
    ALLOWED_COMMISSION_TRANSITIONS,
    PAISA,
    build_dedupe_key,
)
from acom_core.api.errors import AcomApiError

IMPORT_PRIVILEGED_ROLES = ("System Manager", "ACOM Finance")

STATUS_SYNONYMS: dict[str, str] = {
    "pending": "Pending",
    "confirmed": "Confirmed",
    "approved": "Confirmed",
    "paid": "Paid",
    "settled": "Paid",
    "rejected": "Rejected",
    "declined": "Rejected",
    "cancelled": "Rejected",
    "canceled": "Rejected",
    "reversed": "Reversed",
    "clawback": "Reversed",
}

DEFAULT_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "network_conversion_id": ("network_conversion_id", "external_transaction_id", "transaction_id", "conversion_id"),
    "external_order_id": ("external_order_id", "order_id"),
    "conversion_date": ("conversion_date", "transaction_date", "date"),
    "order_value": ("order_value", "gross_order_value", "order_amount"),
    "commission_amount": ("commission_amount", "commission", "payout_amount"),
    "commission_status": ("commission_status", "status"),
    "currency": ("currency",),
    "subid": ("subid", "sub_id", "click_id", "ascsubtag"),
    "product_sku": ("product_sku", "sku", "asin"),
    "payment_reference": ("payment_reference", "payout_reference", "utr"),
    "reversal_reason": ("reversal_reason", "reason"),
}


def _require_import_role() -> None:
    if frappe.session.user == "Guest":
        raise AcomApiError("UNAUTHENTICATED", "Authentication required.", status_code=401)
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection(IMPORT_PRIVILEGED_ROLES):
        raise AcomApiError("FORBIDDEN", "Not permitted.", status_code=403)


def normalize_commission_status(raw_status: Any) -> str:
    if raw_status is None or not str(raw_status).strip():
        return "Pending"
    key = str(raw_status).strip().lower()
    mapped = STATUS_SYNONYMS.get(key)
    if not mapped:
        raise AcomApiError(
            "VALIDATION_ERROR",
            f"Unsupported commission_status '{raw_status}'.",
            status_code=400,
            details={"fields": ["commission_status"], "value": str(raw_status)},
        )
    return mapped


def _parse_decimal_strict(value: Any, field_name: str, *, required: bool) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise AcomApiError(
                "VALIDATION_ERROR",
                f"{field_name} is required.",
                status_code=400,
                details={"fields": [field_name]},
            )
        return None

    if isinstance(value, bool):
        raise AcomApiError(
            "VALIDATION_ERROR",
            f"{field_name} must be a valid decimal number.",
            status_code=400,
            details={"fields": [field_name]},
        )

    try:
        dec = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AcomApiError(
            "VALIDATION_ERROR",
            f"{field_name} must be a valid decimal number.",
            status_code=400,
            details={"fields": [field_name]},
        ) from exc

    if dec.is_nan() or dec.is_infinite():
        raise AcomApiError(
            "VALIDATION_ERROR",
            f"{field_name} must be finite.",
            status_code=400,
            details={"fields": [field_name]},
        )
    if dec < Decimal("0"):
        raise AcomApiError(
            "VALIDATION_ERROR",
            f"{field_name} cannot be negative.",
            status_code=400,
            details={"fields": [field_name]},
        )
    return dec.quantize(PAISA, rounding=ROUND_HALF_UP)


def _parse_date_strict(value: Any, field_name: str) -> str:
    if value is None or not str(value).strip():
        raise AcomApiError(
            "VALIDATION_ERROR",
            f"{field_name} is required.",
            status_code=400,
            details={"fields": [field_name]},
        )
    try:
        parsed = getdate(str(value).strip())
        return parsed.isoformat()
    except Exception as exc:
        raise AcomApiError(
            "VALIDATION_ERROR",
            f"{field_name} must be a valid ISO date (YYYY-MM-DD).",
            status_code=400,
            details={"fields": [field_name]},
        ) from exc


def _load_network_column_map(report_schema_raw: Any) -> dict[str, str]:
    """Read optional column mapping from Affiliate Network.report_schema JSON."""
    if not report_schema_raw:
        return {}
    parsed = report_schema_raw
    if isinstance(report_schema_raw, str):
        try:
            parsed = json.loads(report_schema_raw)
        except json.JSONDecodeError:
            return {}
    if isinstance(parsed, dict):
        columns = parsed.get("columns", parsed)
        if isinstance(columns, dict):
            return {str(k).strip(): str(v).strip() for k, v in columns.items() if k and v}
    return {}


def _extract_field(row: dict[str, Any], canonical: str, custom_map: dict[str, str]) -> Any:
    if canonical in custom_map and custom_map[canonical] in row:
        return row.get(custom_map[canonical])
    for alias in DEFAULT_COLUMN_ALIASES.get(canonical, (canonical,)):
        if alias in row:
            return row.get(alias)
    return None


def _parse_csv_rows(csv_content: str, custom_map: dict[str, str]) -> list[dict[str, Any]]:
    if not isinstance(csv_content, str) or not csv_content.strip():
        raise AcomApiError(
            "VALIDATION_ERROR",
            "csv_content must be a non-empty CSV string.",
            status_code=400,
            details={"fields": ["csv_content"]},
        )

    reader = csv.DictReader(io.StringIO(csv_content.strip()))
    if not reader.fieldnames:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "CSV header row is missing.",
            status_code=400,
            details={"fields": ["csv_content"]},
        )

    headers = {h.strip() for h in reader.fieldnames if h and h.strip()}
    required_canonicals = ("network_conversion_id", "conversion_date", "commission_amount")
    missing_cols: list[str] = []
    for canonical in required_canonicals:
        expected_custom = custom_map.get(canonical)
        aliases = set(DEFAULT_COLUMN_ALIASES[canonical])
        if expected_custom:
            aliases.add(expected_custom)
        if not headers.intersection(aliases):
            missing_cols.append(expected_custom or canonical)

    if missing_cols:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "CSV is missing required columns; import aborted with zero rows written.",
            status_code=400,
            details={"missing_columns": missing_cols},
        )

    rows: list[dict[str, Any]] = []
    for raw_row in reader:
        cleaned = {(k.strip() if k else ""): (v.strip() if isinstance(v, str) else v) for k, v in raw_row.items()}
        if any(val not in (None, "") for val in cleaned.values()):
            rows.append(cleaned)
    return rows


def _normalize_and_validate_rows(
    raw_rows: list[dict[str, Any]],
    *,
    custom_map: dict[str, str],
) -> list[dict[str, Any]]:
    if not isinstance(raw_rows, list) or len(raw_rows) == 0:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Import payload must contain at least one conversion row.",
            status_code=400,
            details={"fields": ["rows"]},
        )

    normalized: list[dict[str, Any]] = []
    for idx, raw_row in enumerate(raw_rows, start=1):
        if not isinstance(raw_row, dict):
            raise AcomApiError(
                "VALIDATION_ERROR",
                f"Row {idx} must be an object.",
                status_code=400,
                details={"row": idx},
            )

        conv_id = _extract_field(raw_row, "network_conversion_id", custom_map)
        if conv_id is None or not str(conv_id).strip():
            raise AcomApiError(
                "VALIDATION_ERROR",
                f"Row {idx}: network_conversion_id (or external_transaction_id) is required.",
                status_code=400,
                details={"row": idx, "fields": ["network_conversion_id"]},
            )

        conv_date = _parse_date_strict(
            _extract_field(raw_row, "conversion_date", custom_map),
            f"row[{idx}].conversion_date",
        )
        commission_amount = _parse_decimal_strict(
            _extract_field(raw_row, "commission_amount", custom_map),
            f"row[{idx}].commission_amount",
            required=True,
        )
        order_value = _parse_decimal_strict(
            _extract_field(raw_row, "order_value", custom_map),
            f"row[{idx}].order_value",
            required=False,
        )
        commission_status = normalize_commission_status(
            _extract_field(raw_row, "commission_status", custom_map)
        )

        payment_ref = _extract_field(raw_row, "payment_reference", custom_map)
        payment_ref = str(payment_ref).strip() if payment_ref is not None and str(payment_ref).strip() else None

        reversal_reason = _extract_field(raw_row, "reversal_reason", custom_map)
        reversal_reason = (
            str(reversal_reason).strip()
            if reversal_reason is not None and str(reversal_reason).strip()
            else None
        )

        if commission_status == "Paid" and not payment_ref:
            raise AcomApiError(
                "VALIDATION_ERROR",
                f"Row {idx}: payment_reference is required when commission_status is Paid.",
                status_code=400,
                details={"row": idx, "fields": ["payment_reference"]},
            )

        if commission_status == "Reversed" and not reversal_reason:
            raise AcomApiError(
                "VALIDATION_ERROR",
                f"Row {idx}: reversal_reason is required when commission_status is Reversed.",
                status_code=400,
                details={"row": idx, "fields": ["reversal_reason"]},
            )

        currency_raw = _extract_field(raw_row, "currency", custom_map)
        currency = str(currency_raw).strip().upper() if currency_raw and str(currency_raw).strip() else "INR"
        if not frappe.db.exists("Currency", currency):
            raise AcomApiError(
                "VALIDATION_ERROR",
                f"Row {idx}: unknown currency '{currency}'.",
                status_code=400,
                details={"row": idx, "fields": ["currency"]},
            )

        subid_raw = _extract_field(raw_row, "subid", custom_map)
        subid = str(subid_raw).strip() if subid_raw is not None and str(subid_raw).strip() else None

        sku_raw = _extract_field(raw_row, "product_sku", custom_map)
        product_sku = str(sku_raw).strip() if sku_raw is not None and str(sku_raw).strip() else None

        ext_order_raw = _extract_field(raw_row, "external_order_id", custom_map)
        ext_order_id = (
            str(ext_order_raw).strip()
            if ext_order_raw is not None and str(ext_order_raw).strip()
            else None
        )

        normalized.append(
            {
                "row_num": idx,
                "network_conversion_id": str(conv_id).strip(),
                "external_order_id": ext_order_id,
                "conversion_date": conv_date,
                "order_value": order_value,
                "commission_amount": commission_amount,
                "commission_status": commission_status,
                "currency": currency,
                "subid": subid,
                "product_sku": product_sku,
                "payment_reference": payment_ref,
                "reversal_reason": reversal_reason,
            }
        )
    return normalized


def _resolve_attribution(
    *,
    network_name: str,
    cookie_window_days: int | None,
    conversion_date: str,
    subid: str | None,
    product_sku: str | None,
) -> dict[str, Any]:
    """Resolve click, product, and campaign attribution per BUSINESS_WORKFLOWS.md W3."""
    if subid:
        click = frappe.db.get_value(
            "Affiliate Click",
            subid,
            ["name", "affiliate_product", "campaign_id", "clicked_at", "attribution_status"],
            as_dict=True,
        )
        if click:
            if cookie_window_days and int(cookie_window_days) > 0:
                click_date = getdate(click["clicked_at"])
                age = date_diff(getdate(conversion_date), click_date)
                if age > int(cookie_window_days):
                    if click["attribution_status"] != "Expired":
                        click_doc = frappe.get_doc("Affiliate Click", click["name"])
                        click_doc.attribution_status = "Expired"
                        click_doc.save(ignore_permissions=True)
                    return {
                        "affiliate_click": None,
                        "affiliate_product": None,
                        "campaign": None,
                        "matched_by": "Unmatched",
                        "needs_manual_review": 1,
                        "raw_subid": subid,
                        "raw_product_sku": product_sku,
                    }

            product_name = click["affiliate_product"]
            campaign_name = click["campaign_id"] or frappe.db.get_value(
                "Affiliate Product", product_name, "campaign"
            )
            if click["attribution_status"] != "Matched":
                click_doc = frappe.get_doc("Affiliate Click", click["name"])
                click_doc.attribution_status = "Matched"
                click_doc.save(ignore_permissions=True)

            return {
                "affiliate_click": click["name"],
                "affiliate_product": product_name,
                "campaign": campaign_name,
                "matched_by": "SubId",
                "needs_manual_review": 0,
                "raw_subid": subid,
                "raw_product_sku": product_sku,
            }

        # Orphan subid: do not crash and do not silently drop — flag for manual review.
        return {
            "affiliate_click": None,
            "affiliate_product": None,
            "campaign": None,
            "matched_by": "Unmatched",
            "needs_manual_review": 1,
            "raw_subid": subid,
            "raw_product_sku": product_sku,
        }

    if product_sku:
        product = frappe.db.get_value(
            "Affiliate Product",
            {"affiliate_network": network_name, "product_sku": product_sku},
            ["name", "campaign"],
            as_dict=True,
        )
        if product:
            return {
                "affiliate_click": None,
                "affiliate_product": product["name"],
                "campaign": product["campaign"],
                "matched_by": "ProductSku",
                "needs_manual_review": 0,
                "raw_subid": None,
                "raw_product_sku": product_sku,
            }

    return {
        "affiliate_click": None,
        "affiliate_product": None,
        "campaign": None,
        "matched_by": "Unmatched",
        "needs_manual_review": 1,
        "raw_subid": subid,
        "raw_product_sku": product_sku,
    }


def import_affiliate_conversions(
    *,
    network: str,
    report_date: str,
    rows: list[dict[str, Any]] | None = None,
    csv_content: str | None = None,
    file_name: str | None = None,
) -> dict[str, Any]:
    """Import affiliate conversions idempotently from JSON rows or CSV content."""
    _require_import_role()

    network_name = (network or "").strip()
    if not network_name or not frappe.db.exists("Affiliate Network", network_name):
        raise AcomApiError(
            "NOT_FOUND",
            f"Affiliate Network '{network_name}' not found.",
            status_code=404,
            details={"fields": ["network"]},
        )

    parsed_report_date = _parse_date_strict(report_date, "report_date")
    net_meta = frappe.db.get_value(
        "Affiliate Network",
        network_name,
        ["name", "cookie_window_days", "report_schema"],
        as_dict=True,
    )
    custom_map = _load_network_column_map(net_meta.get("report_schema"))

    if csv_content is not None and rows is not None:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Provide either rows (JSON) or csv_content (CSV), not both.",
            status_code=400,
        )

    if csv_content is not None:
        source_format = "CSV"
        raw_rows = _parse_csv_rows(csv_content, custom_map)
        canonical_digest_input = f"{network_name}|{parsed_report_date}|CSV|{csv_content}"
    elif rows is not None:
        source_format = "JSON"
        raw_rows = rows
        canonical_digest_input = (
            f"{network_name}|{parsed_report_date}|JSON|"
            f"{json.dumps(rows, sort_keys=True, default=str)}"
        )
    else:
        raise AcomApiError(
            "VALIDATION_ERROR",
            "Either rows or csv_content is required.",
            status_code=400,
            details={"fields": ["rows", "csv_content"]},
        )

    validated_rows = _normalize_and_validate_rows(raw_rows, custom_map=custom_map)

    # Pre-check illegal status transitions on existing records BEFORE creating the batch
    # so invalid reports fail cleanly without partial writes.
    for item in validated_rows:
        dedupe_key = build_dedupe_key(network_name, item["network_conversion_id"])
        existing_row = frappe.db.get_value(
            "Affiliate Conversion",
            {"dedupe_key": dedupe_key},
            ["name", "commission_status", "commission_amount"],
            as_dict=True,
        )
        if existing_row and item["commission_status"] != "Reversed":
            prev_status = existing_row["commission_status"]
            new_status = item["commission_status"]
            allowed = ALLOWED_COMMISSION_TRANSITIONS.get(prev_status, frozenset())
            if new_status not in allowed:
                raise AcomApiError(
                    "ILLEGAL_STATUS_TRANSITION",
                    f"Row {item['row_num']}: illegal transition from '{prev_status}' to '{new_status}' "
                    f"for '{item['network_conversion_id']}'.",
                    status_code=422,
                    details={
                        "row": item["row_num"],
                        "network_conversion_id": item["network_conversion_id"],
                        "from_status": prev_status,
                        "to_status": new_status,
                    },
                )

    content_sha256 = hashlib.sha256(canonical_digest_input.encode("utf-8")).hexdigest()
    batch = frappe.get_doc(
        {
            "doctype": "Affiliate Import Batch",
            "affiliate_network": network_name,
            "report_date": parsed_report_date,
            "source_format": source_format,
            "file_name": (file_name or "").strip() or None,
            "content_sha256": content_sha256,
            "status": "Processing",
            "total_rows": len(validated_rows),
        }
    )
    batch.insert()

    inserted = 0
    updated = 0
    skipped = 0
    unmatched = 0
    errors: list[dict[str, Any]] = []
    affected_ids: list[str] = []

    for item in validated_rows:
        dedupe_key = build_dedupe_key(network_name, item["network_conversion_id"])
        existing_name = frappe.db.get_value(
            "Affiliate Conversion", {"dedupe_key": dedupe_key}, "name"
        )

        # Case 1: Reversal of an existing conversion -> create NEW Reversed row, retain original!
        if existing_name and item["commission_status"] == "Reversed":
            rev_network_id = f"{item['network_conversion_id']}:REV"
            rev_dedupe_key = build_dedupe_key(network_name, rev_network_id)
            if frappe.db.exists("Affiliate Conversion", {"dedupe_key": rev_dedupe_key}):
                skipped += 1
                continue

            orig = frappe.db.get_value(
                "Affiliate Conversion",
                existing_name,
                ["affiliate_click", "affiliate_product", "campaign", "matched_by", "external_order_id"],
                as_dict=True,
            )
            rev_doc = frappe.get_doc(
                {
                    "doctype": "Affiliate Conversion",
                    "affiliate_network": network_name,
                    "network_conversion_id": rev_network_id,
                    "external_order_id": item["external_order_id"] or orig.get("external_order_id"),
                    "conversion_date": item["conversion_date"],
                    "report_date": parsed_report_date,
                    "currency": item["currency"],
                    "order_value": float(item["order_value"]) if item["order_value"] is not None else None,
                    "commission_amount": float(item["commission_amount"]),
                    "commission_status": "Reversed",
                    "affiliate_click": orig.get("affiliate_click"),
                    "affiliate_product": orig.get("affiliate_product"),
                    "campaign": orig.get("campaign"),
                    "matched_by": orig.get("matched_by") or "Unmatched",
                    "reversed_conversion": existing_name,
                    "reversal_reason": item["reversal_reason"],
                    "import_batch": batch.name,
                }
            )
            rev_doc.flags.status_change_note = f"Reversal of {existing_name}: {item['reversal_reason']}"
            rev_doc.insert()
            inserted += 1
            affected_ids.append(rev_doc.name)
            continue

        # Case 2: Existing conversion with same or upgraded status
        if existing_name:
            doc = frappe.get_doc("Affiliate Conversion", existing_name)
            same_status = doc.commission_status == item["commission_status"]
            same_pay_ref = (doc.payment_reference or None) == (
                item["payment_reference"] or doc.payment_reference or None
            )
            if same_status and same_pay_ref:
                skipped += 1
                continue

            doc.commission_status = item["commission_status"]
            doc.report_date = parsed_report_date
            if item["payment_reference"]:
                doc.payment_reference = item["payment_reference"]
            doc.flags.transition_import_batch = batch.name
            doc.flags.status_change_note = (
                f"Report update via batch {batch.name} ({item['commission_status']})"
            )
            doc.save()
            updated += 1
            affected_ids.append(doc.name)
            continue

        # Case 3: Brand-new conversion row
        attribution = _resolve_attribution(
            network_name=network_name,
            cookie_window_days=net_meta.get("cookie_window_days"),
            conversion_date=item["conversion_date"],
            subid=item["subid"],
            product_sku=item["product_sku"],
        )
        if attribution["matched_by"] == "Unmatched":
            unmatched += 1

        new_doc = frappe.get_doc(
            {
                "doctype": "Affiliate Conversion",
                "affiliate_network": network_name,
                "network_conversion_id": item["network_conversion_id"],
                "external_order_id": item["external_order_id"],
                "conversion_date": item["conversion_date"],
                "report_date": parsed_report_date,
                "currency": item["currency"],
                "order_value": float(item["order_value"]) if item["order_value"] is not None else None,
                "commission_amount": float(item["commission_amount"]),
                "commission_status": item["commission_status"],
                "payment_reference": item["payment_reference"],
                "reversal_reason": item["reversal_reason"],
                "import_batch": batch.name,
                **attribution,
            }
        )
        new_doc.flags.status_change_note = f"Imported via batch {batch.name}"
        try:
            new_doc.insert()
        except frappe.DuplicateEntryError:
            skipped += 1
            continue

        inserted += 1
        affected_ids.append(new_doc.name)

    batch.status = "Completed"
    batch.inserted_count = inserted
    batch.updated_count = updated
    batch.skipped_count = skipped
    batch.unmatched_count = unmatched
    batch.error_count = len(errors)
    batch.save()

    return {
        "batch_id": batch.name,
        "network": network_name,
        "report_date": parsed_report_date,
        "source_format": source_format,
        "total_rows": len(validated_rows),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "unmatched": unmatched,
        "errors": errors,
        "conversion_ids": affected_ids,
    }
