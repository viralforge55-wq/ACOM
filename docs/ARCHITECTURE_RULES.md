# ARCHITECTURE RULES

**Status:** BINDING
**Applies to:** every human and every coding agent working in this repository
**Amended only by:** an approved ADR in `docs/ADR/`

If a rule here blocks you, raise it as an ADR proposal. Do not quietly deviate.

---

## 1. SYSTEM BOUNDARIES

### 1.1 The five components

| # | Component | Owns | Must never own |
|---|---|---|---|
| 1 | **ERPNext** (Docker) | Customers, suppliers, items, stock, sales orders, purchase orders, invoices, payments, accounting, taxes | ACOM product-discovery logic |
| 2 | **`acom_core`** (Frappe custom app) | Affiliate domain, dropshipping mapping, product intelligence, AI task state, approval gating | A second accounting engine, a second customer table |
| 3 | **Storefront** (Next.js) | Presentation, cart state, checkout UX | Prices, totals, stock authority, order state |
| 4 | **Ollama** | Local inference only | Business truth; it produces *drafts*, never records |
| 5 | **MariaDB / Redis** | Persistence for (1) and (2) | Direct exposure to any other component |

### 1.2 Hard boundaries

- **MariaDB is never exposed outside its Docker network.** No host port publication, ever.
- **The storefront never writes to ERPNext tables.** It calls APIs. If an operation is required and no API exists, add an API — do not add a database connection.
- **AI never holds a database connection.** It calls a Frappe service method with a declared schema.
- **No component other than ERPNext posts accounting entries.** `acom_core` computes profitability metrics; ERPNext records the money.
- **Affiliate and dropshipping flows never share a checkout path.** Separate code paths, separate records, no shared payment state machine.

### 1.3 Data ownership (single-writer rule)

Every fact has exactly one writer:

| Fact | Sole writer |
|---|---|
| Customer identity | ERPNext |
| Supplier master | ERPNext |
| Item / SKU | ERPNext |
| Selling price | ERPNext Price List |
| Stock quantity | ERPNext (or supplier sync via a service, then ERPNext) |
| Affiliate click | `acom_core` (`Affiliate Click`) |
| Affiliate commission | `acom_core` (imported report), never estimated |
| Payment status | Payment gateway webhook → `acom_core` → ERPNext |
| Order status | ERPNext Sales Order |
| AI task status | `acom_core` (`AI Task`) |
| Profitability metric | Computed, never stored as a mutable source of truth |

---

## 2. TECHNOLOGY DECISIONS

Ratified decisions live in `docs/ADR/`. Summary:

| Decision | Ruling | ADR |
|---|---|---|
| Affiliate engine before dropshipping | **Yes** | 0001 |
| Node-RED | **Deferred**; use Frappe scheduler + Python runner | 0002 |
| Docker data-root location | **C:** (82 GB free; alarm at 25 GB) | 0003 |
| AI model ceiling | 3B resident; 7B on-demand only | 0004 |
| Shopify | Prohibited | — |
| Kubernetes | Prohibited for PoC | — |
| Second ERP / second accounting engine | Prohibited | — |
| Microservice split of `acom_core` | Prohibited until an ADR argues for it | — |
| Mandatory paid cloud AI | Prohibited | — |

**Excluded by policy:** Shopify, paid automation platforms, Kubernetes, unnecessary microservices, multiple competing ERP databases, separate custom accounting software, proprietary AI APIs as mandatory dependencies, extra message brokers when Frappe's queue suffices.

**Optional, only on written justification:** LiteLLM, Qdrant, Playwright, PostgreSQL, Metabase, MinIO, OpenTelemetry.

---

## 3. MODULE RESPONSIBILITIES (`acom_core`)

One Frappe app. Modules map to folders, not to deployments.

```
apps/acom_core/
├── acom_core/
│   ├── affiliate_commerce/         Affiliate Product, Click, Campaign, Conversion, Reconciliation
│   ├── dropshipping_commerce/      Dropshipping Product, supplier mapping, PO draft generation
│   ├── product_intelligence/       Product score, margin calculator, research reports
│   ├── supplier_intelligence/      Supplier Performance, reliability scoring
│   ├── ai_operations/              AI Task, AI Approval Request, agent registry, runners
│   ├── marketing_automation/       Content drafts, campaign records
│   ├── analytics/                  Read-only aggregations for dashboards
│   └── integration_management/     Automation Event, inbound endpoints, HMAC
├── api/                            Whitelisted API surface (see API_CONTRACTS.md)
├── hooks.py
└── patches.txt
```

**Module dependency direction (strict, one-way):**

```
integration_management → ai_operations → product_intelligence → affiliate_commerce / dropshipping_commerce → analytics
```

`analytics` may read from anything. Nothing may import from `analytics`.

---

## 4. NAMING CONVENTIONS

### 4.1 Python (PEP 8, Frappe style)

| Thing | Convention | Example |
|---|---|---|
| Module file | `snake_case.py` | `commission_reconciliation.py` |
| Function | `snake_case` | `reconcile_commissions()` |
| Private helper | `_leading_underscore` | `_validate_totals()` |
| Constant | `UPPER_SNAKE` | `MAX_CLICK_AGE_HOURS = 30` |
| Class (DocType) | `PascalCase`, matches DocType name | `AffiliateProduct` |
| Whitelisted API | `verb_noun` | `create_affiliate_click` |

### 4.2 DocTypes

| Thing | Rule | Example |
|---|---|---|
| DocType name | Title Case, singular | `Affiliate Product` |
| Field | `snake_case` | `commission_rate` |
| Link field | `<target>_` suffix or exact target name | `affiliate_product`, `supplier` |
| Child table field | plural | `items`, `line_items` |
| Status field | always `status`; options are enums below | `status` |
| Autoname | `naming_series` for transactional docs, `field:slug` where a slug exists | `ACLICK-.YYYY.-.#####` |

### 4.3 Status enums (do not invent new values)

```
Affiliate Product.status : Draft | Pending Approval | Published | Paused | Rejected | Expired
Dropshipping Product.status : Draft | Pending Approval | Published | Out of Stock | Paused | Rejected
Affiliate Click.attribution_status : Recorded | Matched | Unmatched | Expired
AI Task.status : Queued | Running | Succeeded | Failed | Rejected | Timed Out
AI Approval Request.approval_status : Pending | Approved | Rejected | Expired
Automation Event.processing_status : Received | Processing | Completed | Failed | Dead Letter
```

PascalCase enum values, not lowercase. New values require an ADR because every dashboard filters on them.

### 4.4 API and JSON

- JSON keys: `snake_case`, matching the DocType field name exactly.
- Booleans: `true`/`false`, never `0`/`1`, never `"yes"`.
- Money: **string decimal**, never float. `"1299.00"`.
- Currency: explicit 3-letter ISO code on every monetary object.
- Timestamps: ISO 8601 with offset, `2026-11-20T14:32:00+05:30`.
- Identifiers: opaque strings, never reused.

### 4.5 TypeScript

| Thing | Convention |
|---|---|
| Component file | `PascalCase.tsx` |
| Hook | `useSomething.ts` |
| Server module | `snake_case.ts` under `lib/server/` |
| Type | `PascalCase`, no `I` prefix |
| Env var | `NEXT_PUBLIC_*` only for genuinely public values |

---

## 5. DATA AND MONEY

- **Money is `Decimal(18,2)` in MariaDB and `decimal.Decimal` in Python, `string` in JSON.** Never `float`. Frappe `Currency` field type is acceptable and preferred.
- **Taxes are not revenue.** GST collected is a liability, never contribution profit.
- **Estimated ≠ confirmed.** `Estimated`, `Pending`, `Confirmed`, `Settled` are distinct states and must be distinct fields or distinct rows.
- Every monetary aggregate on a dashboard must be traceable to transaction rows by drill-through. No bare numbers.
- Avoid `raw SQL`. If a query is unavoidable: parameterised, read-only, in `analytics/`, with a comment explaining why the ORM could not express it.

---

## 6. INTEGRATION RULES

- All inbound internal traffic is authenticated with **HMAC-SHA256 over `timestamp + "." + raw_body`**, secret from env, ±300 s window, nonce store for replay rejection.
- All outbound calls have a timeout, a retry policy with backoff, and a circuit-breaker threshold.
- Every external call is logged with: correlation ID, endpoint, status, latency, attempt number. Never log secrets, tokens, or full customer payloads.
- Webhooks are verified against **raw bytes before parsing**.
- Nothing trusts the browser for price, discount, stock, or totals. Server recomputes; mismatch → reject the checkout.

---

## 7. SECURITY REQUIREMENTS (see SECURITY_POLICY.md)

Non-negotiable summary:

- No `allow_guest` on any endpoint that writes business data.
- Public endpoints are read-only and return whitelisted fields.
- No secret in Git, in logs, in error messages, or in a client bundle.
- Payment gateway signatures verified server-side, replay-safe.
- Session cookies: `HttpOnly`, `Secure` outside localhost, `SameSite=Lax` minimum.
- Dependency additions require license review before merge.

---

## 8. TESTING REQUIREMENTS

- A change is not complete until tests execute and pass. "Should work" is not a result.
- **Domain logic** (margin, scoring, reconciliation, idempotency) requires unit tests.
- **Any endpoint that moves money or changes order state** requires an integration test against the real Frappe test database.
- **Every new DocType** requires: create, validate-fail, permission-denied, and migration tests.
- Coverage floor: **80% on `acom_core` service layer**, 100% of branches in payment and idempotency code.
- Tests never call live payment gateways or live affiliate APIs. Fixtures only.
- Test data is synthetic. No real customer data at any layer.

Required evidence in every completion report — see `TEST_PLAN.md` §6.

---

## 9. VERSION PINNING

- Frappe, ERPNext, India Compliance, MariaDB, and Redis versions are pinned in `infrastructure/docker/`.
- Bumping a pin requires: changelog review, migration test on a copy, and an ADR entry if behaviour changes.
- No `latest` tags. Anywhere. Including helper images.
- Python and Node versions are declared in `infrastructure/docker/` and must match the storefront's runtime.

---

## 10. DEFINITION OF DONE

A work item is done when **all** of these hold:

1. Scope matches the request; nothing extra was built.
2. Code follows §4 naming and §3 module boundaries.
3. Tests exist, run, and pass locally.
4. Security reviewed against §7.
5. No secrets, no real data, no debug leftovers.
6. Changed files and test output reported.
7. Docs updated if an interface or enum changed.
8. If the architecture changed: an approved ADR exists first.

**Not done:** "implemented but untested", "works on my machine, tests fail elsewhere", "architecture adjusted to make it easier".
