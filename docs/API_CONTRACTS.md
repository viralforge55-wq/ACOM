# API CONTRACTS

**Status:** BINDING from Phase 3
**Base (local):** `http://localhost:8000` (Frappe) · `http://localhost:3000` (storefront)
**Content type:** `application/json; charset=utf-8`

Breaking any shape in this document requires a version bump and an ADR.

---

## 0. GLOBAL CONVENTIONS

### 0.1 Envelope

Success:

```json
{ "ok": true, "data": { }, "meta": { "correlation_id": "..." } }
```

Failure:

```json
{
  "ok": false,
  "error": { "code": "PRICE_MISMATCH", "message": "Human readable", "details": { } },
  "meta": { "correlation_id": "..." }
}
```

- `error.code` is a stable `UPPER_SNAKE` machine token. Clients branch on `code`, never on `message`.
- `meta.correlation_id` is present on every response and appears in every server log line for that request.

### 0.2 Money, time, identifiers

| Kind | Representation |
|---|---|
| Money | `{ "amount": "1299.00", "currency": "INR" }` — string decimal, never a JSON number |
| Datetime | ISO 8601 with offset: `2026-11-20T14:32:00+05:30` |
| ID | Opaque string. Never expose a MariaDB integer PK |
| Pagination | `?page=1&page_size=20` (max 100), response `meta.total`, `meta.has_next` |

### 0.3 Status codes

| Code | Meaning |
|---|---|
| 200 | OK |
| 201 | Created |
| 400 | Validation failed → `VALIDATION_ERROR` |
| 401 | Not authenticated → `UNAUTHENTICATED` |
| 403 | Not permitted → `FORBIDDEN` |
| 404 | Not found → `NOT_FOUND` |
| 409 | Conflict / duplicate → `DUPLICATE`, `IDEMPOTENCY_CONFLICT` |
| 422 | Business rule violated → `PRICE_MISMATCH`, `OUT_OF_STOCK`, `PRODUCT_UNAVAILABLE` |
| 429 | Rate limited → `RATE_LIMITED` (with `Retry-After`) |
| 500 | Server error → `INTERNAL_ERROR` (never leaks a traceback) |

---

## 1. PUBLIC CATALOG (read-only, no auth)

### `GET /api/catalog`

Query: `page`, `page_size`, `category`, `sales_type` (`AFFILIATE`|`DROPSHIP`), `sort` (`newest`|`popular`|`price_asc`|`price_desc`), `q`.

```json
{
  "ok": true,
  "data": {
    "items": [
      {
        "id": "APROD-00012",
        "slug": "stainless-steel-water-bottle-1l",
        "title": "Stainless Steel Water Bottle 1L",
        "sales_type": "AFFILIATE",
        "category": { "slug": "kitchen", "name": "Kitchen" },
        "image_url": "https://.../bottle.webp",
        "display_price": { "amount": "799.00", "currency": "INR" },
        "marketplace": "Amazon",
        "badge": "Trending",
        "cta_label": "View Deal"
      }
    ]
  },
  "meta": { "total": 214, "page": 1, "page_size": 20, "has_next": true, "correlation_id": "..." }
}
```

**AFFILIATE** items carry `cta_label: "View Deal"` and **no** `add_to_cart` capability.
**DROPSHIP** items carry `cta_label: "Add to Cart"` and a live `availability` object.

### `GET /api/products/{slug}`

Returns the full public record. Dropship products additionally include:

```json
{
  "sales_type": "DROPSHIP",
  "price": { "amount": "1499.00", "currency": "INR" },
  "availability": { "in_stock": true, "quantity_band": "5+", "ships_in_days": 3 },
  "hsn_category": "Plastic Household",
  "return_policy_summary": "7-day replacement on damage"
}
```

Affiliate products additionally include `affiliate_disclosure` (required text) and `view_deal_url` (a **server-side redirector path**, never the raw affiliate URL — see §2).

**Never returned by any public endpoint:** `supplier_cost`, `supplier`, `supplier_sku`, `contribution_profit`, `contribution_margin_pct`, `commission_rate`, `commission_amount`, `expected_return_rate`, `payment_fee_percent`, raw affiliate URL.

### `GET /api/categories`

Flat list with `slug`, `name`, `product_count`, `parent` (nullable).

---

## 2. AFFILIATE CLICK

### `POST /api/affiliate/click`

Rate limit: **60/hour per session**, 600/hour per IP.

Request:

```json
{
  "product_slug": "stainless-steel-water-bottle-1l",
  "session_id": "s_7f3c1a9e...",
  "source": "google",
  "medium": "organic",
  "landing_path": "/products/stainless-steel-water-bottle-1l"
}
```

Response `201`:

```json
{ "ok": true, "data": { "click_id": "b6f1...", "redirect_url": "/go/b6f1..." } }
```

Rules:

- `clicked_at` is server time. Any client-supplied timestamp is ignored.
- `session_id` is validated for format only; it is not an identity.
- Server persists the click, then returns a same-origin redirector path. The client navigates there; `/go/{click_id}` issues a `302` to the affiliate URL with the required tracking parameter and `rel="sponsored nofollow"` semantics documented for crawlers.
- Duplicate submissions within 2 s for the same `(session_id, product)` are deduplicated.
- A click **never** creates revenue.

---

## 3. CART AND CHECKOUT (dropshipping only)

### `POST /api/cart/validate`

No auth required to validate; identity required to check out.

Request:

```json
{ "items": [ { "product_slug": "bamboo-cutlery-set", "quantity": 2 } ] }
```

Response — the server's authoritative view:

```json
{
  "ok": true,
  "data": {
    "lines": [
      {
        "product_slug": "bamboo-cutlery-set",
        "title": "Bamboo Cutlery Set",
        "quantity": 2,
        "unit_price": { "amount": "549.00", "currency": "INR" },
        "line_total": { "amount": "1098.00", "currency": "INR" },
        "available": true
      }
    ],
    "subtotal": { "amount": "1098.00", "currency": "INR" },
    "shipping": { "amount": "0.00", "currency": "INR" },
    "tax": { "amount": "0.00", "currency": "INR" },
    "total": { "amount": "1098.00", "currency": "INR" },
    "cart_token": "ct_9a2b..."
  }
}
```

- The client must not compute totals. It renders what this returns.
- `cart_token` is a server-signed digest of the priced cart, valid 15 minutes. Any price change invalidates it.

### `POST /api/checkout`

Auth: required (`401` otherwise). Headers: `Idempotency-Key: <uuid v4>` (**required**).

Request:

```json
{
  "cart_token": "ct_9a2b...",
  "customer": { "name": "...", "email": "...", "phone": "..." },
  "shipping_address": { "line1": "...", "city": "...", "state": "...", "pincode": "...", "country": "IN" },
  "payment_method": "gateway"
}
```

Response `201`:

```json
{
  "ok": true,
  "data": {
    "checkout_id": "CHK-2026-00041",
    "status": "PendingPayment",
    "amount": { "amount": "1098.00", "currency": "INR" },
    "payment": { "provider": "razorpay", "order_ref": "order_XYZ", "checkout_token": "..." }
  }
}
```

Failure cases:

| Condition | Code | HTTP |
|---|---|---|
| `cart_token` expired or digest mismatch | `CART_EXPIRED` | 422 |
| Server price ≠ cart price | `PRICE_MISMATCH` | 422 |
| Product not `Published` | `PRODUCT_UNAVAILABLE` | 422 |
| Supplier mapping missing | `SUPPLIER_MAPPING_MISSING` | 422 (server-side defect — alert) |
| Stock insufficient | `OUT_OF_STOCK` | 422 |
| Same `Idempotency-Key` reused with a different body | `IDEMPOTENCY_CONFLICT` | 409 |
| Same `Idempotency-Key` reused with the same body | — | 200, returns the original `checkout_id` |

**The server never accepts a price, total, discount, or currency from the request body** (except as a value it then rejects on mismatch).

---

## 4. PAYMENT WEBHOOK (server-to-server only)

### `POST /api/internal/payments/webhook`

- No session auth. Authentication is the **signature**.
- Verification over the **raw bytes** before JSON parsing.
- Headers: `X-Signature`, `X-Timestamp`, `X-Event-Id`.

Rules:

1. `HMAC_SHA256(secret, f"{timestamp}.{raw_body}")` must match `X-Signature` (constant-time compare).
2. `|now − timestamp| ≤ 300 s`, else `WEBHOOK_STALE`.
3. `X-Event-Id` inserted into a unique-indexed table; a repeat is `200` with `duplicate: true` and **no** state change.
4. `amount`, `currency`, and `order_ref` must match the pending checkout, else `WEBHOOK_MISMATCH` + alert.
5. On success: write `Automation Event(payment.confirmed)` in the same transaction. Sales Order creation happens in the consumer, not here.
6. Always respond `200` for a correctly-signed duplicate; non-200 triggers gateway retries, which is worse.

---

## 5. INTERNAL ENDPOINTS

All require: `Authorization: Bearer <internal-token>` **and** an HMAC signature over the body. Scope-checked per endpoint. Rate limited.

| Endpoint | Body | Purpose |
|---|---|---|
| `POST /api/internal/ai/result` | `{ task_id, output, schema_version }` | Agent returns a validated result |
| `POST /api/internal/supplier/sync` | `{ supplier, stock: [{supplier_sku, qty, cost?}] }` | Stock/price sync |
| `POST /api/internal/affiliate/import` | `{ network, report_date, rows: [...] }` | Conversion import |
| `POST /api/internal/automation/event` | `{ event_type, idempotency_key, payload }` | Outbox injection |

- They are **not** exposed through the storefront. Bind to localhost only.
- `ai/result` rejects an output that fails schema validation, with `SCHEMA_INVALID` and the failing pointer.
- `supplier/sync` may update `supplier_stock`, **never** `selling_price` or `supplier_cost` without an approval record.
- `affiliate/import` is idempotent on `(network, network_conversion_id)`; returns `{ inserted, skipped, errors }`.
- `automation/event` returns `409 DUPLICATE` when `idempotency_key` already exists.

---

## 6. CUSTOMER-SCOPED

### `GET /api/orders/{order_id}`

Auth: owner only, else `403` (not `404` — do not leak existence).

```json
{
  "ok": true,
  "data": {
    "order_id": "SO-2026-00041",
    "status": "Shipped",
    "placed_at": "2026-11-18T10:12:00+05:30",
    "lines": [ { "title": "...", "quantity": 2, "unit_price": { } } ],
    "total": { "amount": "1098.00", "currency": "INR" },
    "fulfillment": { "carrier": "Delhivery", "tracking_number": "...", "tracking_url": "...", "estimated_delivery": "2026-11-24" }
  }
}
```

Status enum: `PendingPayment`, `Paid`, `Processing`, `AwaitingSupplier`, `Shipped`, `Delivered`, `Cancelled`, `Refunded`.

### `POST /api/support/tickets`

```json
{ "order_id": "SO-2026-00041", "category": "delivery", "message": "..." }
```

Returns `{ ticket_id, status: "Open" }`. Categorisation by AI is advisory only; the ticket exists regardless of AI availability.

---

## 7. ERROR CODE REGISTRY

| Code | HTTP | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Field-level failure; `details.fields` lists them |
| `UNAUTHENTICATED` | 401 | No/expired session |
| `FORBIDDEN` | 403 | Authenticated, not permitted |
| `NOT_FOUND` | 404 | Missing |
| `DUPLICATE` | 409 | Unique constraint |
| `IDEMPOTENCY_CONFLICT` | 409 | Key reused with different body |
| `CART_EXPIRED` | 422 | `cart_token` invalid |
| `PRICE_MISMATCH` | 422 | Client/server price divergence |
| `PRODUCT_UNAVAILABLE` | 422 | Not published |
| `OUT_OF_STOCK` | 422 | Supplier stock insufficient |
| `SUPPLIER_MAPPING_MISSING` | 422 | Data integrity defect |
| `WEBHOOK_STALE` | 400 | Timestamp outside window |
| `WEBHOOK_MISMATCH` | 400 | Amount/currency/ref mismatch |
| `SCHEMA_INVALID` | 422 | AI output failed schema |
| `RATE_LIMITED` | 429 | Slow down |
| `INTERNAL_ERROR` | 500 | Unexpected; logged only |

---

## 8. CONTRACT RULES

1. **Additive changes only** within a major version. Removing or retyping a field is breaking.
2. A new enum value is breaking for clients that exhaustively switch — announce it in the changelog.
3. Never return `null` where an object is documented. Omit the key or return an empty object.
4. Every endpoint that mutates must be safe to retry with the same `Idempotency-Key`.
5. Timestamps are server-generated. Client timestamps are diagnostics only.
6. Any endpoint added must be listed here **before** implementation lands.
