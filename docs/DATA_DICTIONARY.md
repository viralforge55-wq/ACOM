# DATA DICTIONARY

**Status:** BINDING once Phase 2 begins
**Scope:** `acom_core` DocTypes and the fields they expose
**Rule:** every field named here is authoritative. Adding or renaming a field requires updating this file and, if the interface changes, `API_CONTRACTS.md`.

Field types use Frappe naming: `Data`, `Int`, `Float`, `Currency`, `Percent`, `Check` (0/1), `Select`, `Link`, `Table`, `Date`, `Datetime`, `Small Text`, `Text`, `Long Text`, `Attach`, `JSON`.

---

## 1. CONVENTIONS

| Concern | Rule |
|---|---|
| Money | `Currency` field type. Never `Float`. Every DocType with money declares `currency` or inherits it from a link. |
| Percentage | `Percent` (stores 0–100). Commission `12.5` means 12.5%. |
| Rates | Stored as percent; **computed amounts** stored separately and never derived at read time for historical records. |
| Dates | `Datetime` in site timezone (`Asia/Kolkata`). `Date` only for calendar-only values (verification date). |
| Derived values | Recompute on save; never trust a derived value from the client. |
| Deletion | Transactional records are cancelled, not deleted. `Affiliate Click` and `Automation Event` are never deleted (retention purge excepted). |
| Naming series | Declared per DocType below; must match `naming_series` options in the JSON. |
| Owner/audit | Frappe's `owner`, `creation`, `modified`, `modified_by` are mandatory — do not disable. |

---

## 2. AFFILIATE PRODUCT

Sales type: `AFFILIATE`. Points at an external marketplace; **never** an inventory item.

| Field | Type | Req | Notes |
|---|---|---|---|
| `naming_series` | Select | ✔ | `APROD-.#####` |
| `product_name` | Data | ✔ | Display name; max 140 |
| `slug` | Data | ✔ | Unique, lowercase, hyphenated; immutable after insert |
| `product_sku` | Data | ✔ | Marketplace's own SKU/ASIN. Not an ERPNext Item Code |
| `marketplace` | Select | ✔ | `Amazon`, `Flipkart`, `Meesho`, `Myntra`, `Ajio`, `Other` |
| `affiliate_network` | Link → `Affiliate Network` | ✔ | |
| `affiliate_url` | Data | ✔ | Validated as http(s); must contain the network's tracking parameter |
| `canonical_url` | Data |  | The plain product URL, for reference and display |
| `category` | Link → `Item Group` | ✔ | Reuses ERPNext taxonomy deliberately |
| `commission_rate` | Percent | ✔ | 0–100 |
| `commission_type` | Select | ✔ | `Percentage`, `Flat`, `Tiered`, `Unknown` |
| `commission_flat_amount` | Currency |  | Required when `commission_type = Flat` |
| `currency` | Link → `Currency` | ✔ | Default `INR` |
| `campaign` | Link → `Affiliate Campaign` |  | |
| `status` | Select | ✔ | `Draft`, `Pending Approval`, `Published`, `Paused`, `Rejected`, `Expired` |
| `last_verified_date` | Date |  | Last time a human or agent confirmed the link and price |
| `verification_method` | Select |  | `Manual`, `Agent`, `Report` |
| `display_price` | Currency |  | Indicative only; storefront must show "price may change" |
| `image` | Attach Image |  | Local copy or approved CDN URL |
| `short_description` | Small Text |  | ≤ 300 chars |
| `long_description` | Text Editor |  | Sanitised HTML only |
| `pros` / `cons` | Table → `Product Highlight` |  | |
| `seo_title` / `seo_description` | Data / Small Text |  | |
| `disclosure_required` | Check | ✔ | Default 1; must render on the page |
| `content_review_status` | Select |  | `Not Reviewed`, `Approved`, `Needs Changes` |

**Validation rules**

1. `affiliate_url` must be `http`/`https` and must not be a `javascript:` or `data:` URL.
2. Publishing requires `last_verified_date` within 30 days and `content_review_status = Approved`.
3. `commission_rate` alone never produces a revenue record. Revenue exists only via `Affiliate Conversion`.
4. An `Affiliate Product` must never reference an ERPNext `Item` or create stock.

---

## 3. AFFILIATE CLICK

Append-only telemetry. No PII.

| Field | Type | Req | Notes |
|---|---|---|---|
| `click_id` | Data | ✔ | UUIDv4, unique, generated server-side. Sole identifier |
| `affiliate_product` | Link → `Affiliate Product` | ✔ | |
| `campaign_id` | Data |  | Copied from product's campaign at click time |
| `source` | Data |  | `utm_source` allowlisted values only |
| `medium` | Data |  | `utm_medium` |
| `referrer` | Data |  | Truncated to 512 chars; **host only** if it exceeds |
| `landing_path` | Data |  | Storefront path that produced the click |
| `session_id` | Data | ✔ | Random anonymous ID, rotated 30 days. Not a fingerprint |
| `clicked_at` | Datetime | ✔ | Server time, never client-supplied |
| `attribution_status` | Select | ✔ | `Recorded`, `Matched`, `Unmatched`, `Expired` |
| `is_bot_suspected` | Check |  | Heuristic flag; excluded from reporting when set |
| `user_agent_family` | Data |  | Coarse (`Chrome`, `Safari`, `Bot`) — no full UA string |

**Rules**

- **No** IP address, no email, no phone, no precise location, no cookie beyond `session_id`.
- Immutable. Corrections are new fields (`attribution_status`), never edits to `clicked_at`.
- A click is **never** a sale. `attribution_status` never becomes `Converted`; conversion lives in `Affiliate Conversion`.

---

## 4. AFFILIATE CONVERSION

Imported from an authorised network report. The only source of affiliate revenue.

| Field | Type | Req | Notes |
|---|---|---|---|
| `naming_series` | Select | ✔ | `ACONV-.YYYY.-.#####` |
| `affiliate_product` | Link → `Affiliate Product` |  | May be unresolved at import |
| `affiliate_click` | Link → `Affiliate Click` |  | Matched where the network supplies a sub-ID |
| `network_conversion_id` | Data | ✔ | **Unique** with `affiliate_network` — the idempotency key |
| `affiliate_network` | Link → `Affiliate Network` | ✔ | |
| `external_order_id` | Data |  | Marketplace order reference, if provided |
| `conversion_date` | Date | ✔ | From the report |
| `report_date` | Date | ✔ | Report period |
| `order_value` | Currency |  | Gross order value as reported |
| `commission_amount` | Currency | ✔ | As reported. Never estimated |
| `commission_status` | Select | ✔ | `Pending`, `Confirmed`, `Rejected`, `Paid`, `Reversed` |
| `payment_reference` | Data |  | Network payout reference when `Paid` |
| `matched_by` | Select |  | `SubId`, `ProductSku`, `Manual`, `Unmatched` |
| `import_batch` | Link → `Affiliate Import Batch` | ✔ | Traceability back to the file |

**Rules**

- `commission_status = Pending` is **not revenue**. Only `Confirmed` and `Paid` enter confirmed-revenue reporting.
- `Reversed` requires a reason and is a new row, not an edit.
- Import is idempotent on `(affiliate_network, network_conversion_id)`.

---

## 5. AFFILIATE NETWORK

| Field | Type | Req | Notes |
|---|---|---|---|
| `network_name` | Data | ✔ | Unique |
| `slug` | Data | ✔ | Unique |
| `program_type` | Select | ✔ | `Marketplace`, `Network`, `Direct` |
| `report_format` | Select | ✔ | `CSV`, `XLSX`, `API` |
| `report_schema` | JSON |  | Column mapping for import |
| `payout_cycle` | Select |  | `Weekly`, `BiWeekly`, `Monthly`, `Net30`, `Net60` |
| `cookie_window_days` | Int |  | Attribution window, for reference only |
| `tracking_param` | Data |  | Required query param key in `Affiliate Product.affiliate_url` (e.g. `tag`, `affid`) |
| `status` | Select | ✔ | `Active`, `Paused`, `Terminated` |
| `terms_notes` | Small Text |  | Attribution/disclosure constraints that matter operationally |

### 5.1 Supporting Lookup & Child DocTypes (referenced by §2)

- **`Affiliate Campaign`** (`ACAMP-.#####`): `campaign_name` (Data, req, unique), `slug` (Data, req, unique, immutable), `affiliate_network` (Link → `Affiliate Network`), `status` (`Draft` | `Active` | `Paused` | `Ended`), `start_date` / `end_date` (Date), `utm_campaign` (Data), `notes` (Small Text).
- **`Product Highlight`** (child table for `Affiliate Product.pros` / `cons`): `text` (Data, req, max 200), `sort_order` (Int).

---

## 6. DROPSHIPPING PRODUCT

Sales type: `DROPSHIP`. **Must** link to a real ERPNext Item and Supplier.

| Field | Type | Req | Notes |
|---|---|---|---|
| `naming_series` | Select | ✔ | `DPROD-.#####` |
| `product_name` | Data | ✔ | |
| `slug` | Data | ✔ | Unique, immutable |
| `erpnext_item` | Link → `Item` | ✔ | Selling entity. Item Code ≠ Supplier SKU |
| `supplier` | Link → `Supplier` | ✔ | |
| `supplier_sku` | Data | ✔ | Supplier's own identifier |
| `supplier_cost` | Currency | ✔ | **Never exposed publicly** |
| `selling_price` | Currency | ✔ | Must equal the active ERPNext Price List rate at publish |
| `price_list` | Link → `Price List` | ✔ | Source of truth for the sold price |
| `shipping_cost` | Currency | ✔ | Inbound-to-customer cost |
| `packaging_cost` | Currency |  | Default from settings |
| `payment_fee_percent` | Percent |  | Default from settings |
| `expected_return_rate` | Percent |  | Used for contribution profit |
| `hsn_code` | Data | ✔ | India GST |
| `gst_rate` | Percent | ✔ | |
| `supplier_stock` | Int |  | Last known |
| `last_stock_sync` | Datetime |  | |
| `lead_time_days` | Int |  | Supplier dispatch SLA |
| `status` | Select | ✔ | `Draft`, `Pending Approval`, `Published`, `Out of Stock`, `Paused`, `Rejected` |
| `contribution_profit` | Currency |  | **Computed on save**, read-only |
| `contribution_margin_pct` | Percent |  | **Computed on save**, read-only |
| `content_review_status` | Select |  | `Not Reviewed`, `Approved`, `Needs Changes` |

**Validation rules**

1. `erpnext_item` and `supplier` must exist and be enabled.
2. `selling_price` must match the active `Price List` rate within tolerance 0.00 — mismatch blocks publish.
3. `contribution_profit < 0` blocks publish unless `status = Rejected`; a negative-margin product may exist as a draft but never go live.
4. Stock sync never overwrites `selling_price`.
5. `supplier_cost` must never appear in any public API response.

**Computed fields**

```
contribution_profit =
      selling_price
    - supplier_cost
    - shipping_cost
    - (packaging_cost or 0)
    - (selling_price * payment_fee_percent / 100)
    - (selling_price * expected_return_rate / 100 * return_cost_factor)
```

`return_cost_factor` (default `1.0`) accounts for return handling cost as a multiple of unit contribution loss. Stored in `ACOM Settings`.

`contribution_margin_pct = contribution_profit / selling_price * 100`, guarded against zero.

Taxes (`gst_rate`) are **excluded** from this calculation. GST is a pass-through liability.

---

## 7. SUPPLIER PERFORMANCE

One row per supplier per evaluation period. Historical rows retained.

| Field | Type | Req | Notes |
|---|---|---|---|
| `supplier` | Link → `Supplier` | ✔ | |
| `period_start` / `period_end` | Date | ✔ | Unique together with `supplier` |
| `orders_received` | Int | ✔ | |
| `orders_fulfilled` | Int | ✔ | |
| `orders_cancelled` | Int | ✔ | |
| `orders_returned` | Int | ✔ | |
| `avg_dispatch_hours` | Float |  | From PO submit → tracking |
| `cancellation_rate` | Percent |  | Computed |
| `return_rate` | Percent |  | Computed |
| `quality_issues` | Int |  | Count of confirmed defect complaints |
| `reliability_score` | Float |  | 0–100, computed; see below |
| `notes` | Small Text |  | Evidence for manual overrides |

**Reliability score**

```
score = 100
      - (cancellation_rate * 2.0)
      - (return_rate * 2.5)
      - (quality_issues / max(orders_fulfilled, 1) * 100 * 1.5)
      - dispatch_penalty
```

`dispatch_penalty` = 0 when `avg_dispatch_hours <= 48`, scaling linearly to 15 at 120 h.
Clamp to `[0, 100]`. A manual override requires `notes` and is an approval-queue event.

---

## 8. AI TASK

| Field | Type | Req | Notes |
|---|---|---|---|
| `task_id` | Data | ✔ | UUID, unique |
| `task_type` | Select | ✔ | `ProductResearch`, `ContentGeneration`, `SupplierAnalysis`, `Classification`, `Report`, `Reconciliation` |
| `agent_id` | Data | ✔ | Registry key, e.g. `product_hunter` |
| `input_reference` | Data |  | DocType+name or JSON pointer |
| `input_hash` | Data | ✔ | SHA-256 of canonical input; dedupe key |
| `model` | Data | ✔ | Exact model tag, e.g. `qwen2.5:3b-instruct` |
| `status` | Select | ✔ | `Queued`, `Running`, `Succeeded`, `Failed`, `Rejected`, `Timed Out` |
| `retry_count` | Int | ✔ | Default 0, cap from settings |
| `max_retries` | Int | ✔ | Default 2 |
| `created_at` / `started_at` / `completed_at` | Datetime |  | |
| `duration_ms` | Int |  | |
| `output_reference` | Data |  | Path/name of produced record |
| `output_validated` | Check |  | Schema validation result |
| `error_code` / `error_details` | Data / Small Text |  | Machine code + truncated detail |
| `prompt_tokens` / `completion_tokens` | Int |  | For cost/size tracking |
| `correlation_id` | Data | ✔ | Ties to the originating event |

**Rules**

- `input_hash` + `agent_id` + `task_type` is the dedupe key; a duplicate within the TTL returns the existing task.
- `Succeeded` requires `output_validated = 1`.
- Failure never blocks a Frappe request. The request enqueues; the worker fails; the founder sees it in the approval/exception queue.

---

## 9. AI APPROVAL REQUEST

| Field | Type | Req | Notes |
|---|---|---|---|
| `request_id` | Data | ✔ | UUID |
| `action_type` | Select | ✔ | `PublishProduct`, `SubmitPurchaseOrder`, `IssueRefund`, `PriceChange`, `SupplierOnboarding`, `ContentPublish` |
| `related_doctype` / `related_name` | Link / Data | ✔ | |
| `ai_task` | Link → `AI Task` |  | Originating task |
| `recommendation` | Long Text | ✔ | What the agent proposes, in plain language |
| `rationale` | Long Text |  | Evidence and numbers |
| `estimated_financial_impact` | Currency |  | Signed; outflow negative |
| `risk_level` | Select | ✔ | `Low`, `Medium`, `High` |
| `approval_status` | Select | ✔ | `Pending`, `Approved`, `Rejected`, `Expired` |
| `approved_by` | Link → `User` |  | Must be a human with the right role |
| `approval_timestamp` | Datetime |  | |
| `decision_note` | Small Text |  | Required on `Rejected` |
| `expires_at` | Datetime |  | Auto-expire, default 72 h |

**Rules**

- `estimated_financial_impact` above the configured threshold **always** requires `High` risk and explicit approval.
- An agent may never set `approval_status`. Only a human session may.
- Expired requests cannot be approved retroactively; a new request is raised.

---

## 10. AUTOMATION EVENT

Outbox. The reliability backbone.

| Field | Type | Req | Notes |
|---|---|---|---|
| `event_id` | Data | ✔ | UUID |
| `event_type` | Data | ✔ | e.g. `payment.confirmed`, `order.created` |
| `source` | Select | ✔ | `Storefront`, `ERPNext`, `PaymentGateway`, `AffiliateImport`, `Scheduler`, `Agent` |
| `aggregate_doctype` / `aggregate_name` | Data |  | What the event is about |
| `idempotency_key` | Data | ✔ | **Unique index** |
| `payload` | JSON | ✔ | Schema-validated per `event_type` |
| `processing_status` | Select | ✔ | `Received`, `Processing`, `Completed`, `Failed`, `Dead Letter` |
| `retry_count` | Int | ✔ | |
| `next_attempt_at` | Datetime |  | Backoff schedule |
| `error_details` | Small Text |  | |
| `created_at` / `processed_at` | Datetime | ✔ | |

**Rules**

- Written in the **same transaction** as the business record it describes.
- Consumers are idempotent; re-delivery is expected, not exceptional.
- `Dead Letter` requires founder visibility on the dashboard. Events never disappear silently.
- Retention: 90 days after `Completed`.

---

## 11. ACOM SETTINGS (Single DocType)

| Field | Purpose |
|---|---|
| `payment_fee_percent` | Default gateway fee used in margin math |
| `packaging_cost_default` | Default per-order packaging |
| `return_cost_factor` | Multiplier for expected return cost |
| `target_contribution_margin_pct` | Research target, default 35 — a guide, not a gate |
| `approval_threshold_amount` | Above this, financial impact requires explicit approval |
| `affiliate_click_retention_days` | Default 180 |
| `affiliate_disclosure_text` | Default affiliate disclosure text returned on public product detail APIs |
| `ai_max_retries` / `ai_task_timeout_seconds` | Agent runtime limits |
| `stale_event_minutes` | Dead-letter threshold |

---

## 12. RELATIONSHIPS

```
Affiliate Network 1─n Affiliate Product 1─n Affiliate Click
                                  │
                                  └─n Affiliate Conversion ─n─ Affiliate Import Batch

Supplier 1─n Dropshipping Product n─1 Item (ERPNext)
                     │
                     └─1 Price List (rate authority)

Supplier 1─n Supplier Performance

AI Task 1─n AI Approval Request
Automation Event ──(references)── any aggregate
```

---

## 13. FIELDS THAT MUST NEVER LEAVE THE SERVER

A public API leak of any of these is a security defect (G3):

`supplier_cost` · `supplier` · `supplier_sku` · `contribution_profit` · `contribution_margin_pct` · `payment_fee_percent` · `expected_return_rate` · `commission_amount` · `commission_status` · `network_conversion_id` · `payload` · `error_details` · `owner` metadata on private docs · any `AI Task` or `AI Approval Request` field.
