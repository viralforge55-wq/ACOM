# BUSINESS WORKFLOWS

**Status:** BINDING specification of behaviour
**Implementation:** Phase 2–7 in `acom_core`
**Rule:** a workflow is not complete until its failure path is implemented and tested.

Every workflow below states: trigger, happy path, failure paths, and the invariants that must hold. Invariants are testable and appear in `TEST_PLAN.md`.

---

## W1 — PRODUCT RESEARCH (AI-assisted, human-decided)

**Trigger:** manual founder request, or a weekly scheduled sweep of a target category.

**Happy path**

1. `Product Research Request` created with category, budget band, and constraints.
2. `AI Task(ProductResearch)` enqueued (`long` queue).
3. Agent produces JSON conforming to `ai/schemas/product_research.schema.json`.
4. Schema validated. Invalid → task `Rejected`, no side effects.
5. Valid → draft `Affiliate Product` or `Dropshipping Product` created with `status = Draft`.
6. Score computed per §4 weights. Margin computed per `DATA_DICTIONARY` §6.
7. If margin ≥ target and score ≥ threshold → `AI Approval Request(PublishProduct)`.
8. Founder approves → `status = Pending Approval` → content workflow (W2).

**Failure paths**

| Failure | Behaviour |
|---|---|
| Ollama unreachable | Task `Failed`, retry ×2 with backoff, then approval-queue alert |
| Invalid JSON | Task `Rejected`; raw output retained for prompt improvement |
| Product already exists (by SKU) | Merge into existing draft; no duplicate |
| Claim unverifiable (price, spec) | Product flagged `content_review_status = Needs Changes`, never auto-published |

**Invariants**

- No product reaches `Published` without a human approval record.
- Research output never writes a price that becomes the selling price without founder confirmation.

---

## W2 — CONTENT GENERATION AND PUBLICATION

**Trigger:** product in `Pending Approval` or a `ContentPublish` change request.

**Happy path:** agent drafts title, description, bullets, SEO → written to draft fields → `content_review_status = Needs Changes` → founder reviews → `Approved` → `status = Published` → `last_verified_date` set.

**Rules**

- AI output is a **draft**. Publication is a human act (until Phase 8, and even then gated by approval threshold).
- No claim about delivery time, warranty, or certification unless present in the supplier or marketplace data.
- Affiliate pages must render the disclosure before the CTA.
- Bulk publishing is prohibited (`MASTER_BLUEPRINT` §13). Rate-limited to a small daily cap.

**Failure:** ambiguous or unsupported claim → `Needs Changes`, with the specific sentence flagged.

---

## W3 — AFFILIATE CLICK AND ATTRIBUTION

**Trigger:** customer completes a click on `View Deal`.

**Happy path**

1. Storefront `POST /api/affiliate/click` (W1 in `API_CONTRACTS` §2).
2. Server generates `click_id`, records `Affiliate Click` with `attribution_status = Recorded`.
3. Client is redirected to `/go/{click_id}` → `302` to the affiliate URL with sub-ID `click_id`.
4. Network later reports a conversion carrying that sub-ID.
5. Import matches it → `Affiliate Conversion` with `matched_by = SubId`, click → `Matched`.

**Failure paths**

| Failure | Behaviour |
|---|---|
| Bot suspected | Recorded, excluded from reporting, not in denominators |
| No sub-ID returned by network | Conversion imported `Unmatched`; manual reconciliation queue |
| Click older than network's window | `Expired`; conversion cannot be attributed |
| Duplicate click within 2 s | Deduplicated; original retained |
| Affiliate URL invalid or blocked | Click not recorded; product auto-`Paused` + alert |

**Invariants**

- A click is never revenue. `Affiliate Click` has no money field.
- At most one `Affiliate Conversion` per `(network, network_conversion_id)`.

---

## W4 — AFFILIATE RECONCILIATION

**Trigger:** network report available (scheduled check), or manual import.

**Happy path**

1. Report uploaded → `Affiliate Import Batch` created.
2. Parse → validate columns against `Affiliate Network.report_schema`.
3. Upsert conversions, idempotent on `(network, network_conversion_id)`.
4. Match to clicks/products.
5. Commission enters `Pending`.
6. Later report marks `Confirmed`, then `Paid` with a payout reference.
7. Reconciliation compares: expected commission vs confirmed vs paid vs bank credit.

**Failure paths**

- Column mismatch → batch `Failed`, nothing partially written.
- Orphan conversion (unknown product) → imported `Unmatched`, queued for manual mapping.
- `Reversed` status → new row with reason; original retained.
- Payout total ≠ sum of `Paid` rows → reconciliation exception, founder alert.

**Invariants**

- `Pending` never appears as revenue on the CEO dashboard.
- Every rupee of affiliate revenue traces to one imported conversion row.
- Re-importing the same file changes nothing.

---

## W5 — DROPSHIPPING ORDER

**Trigger:** customer submits checkout.

**Happy path**

1. `POST /api/cart/validate` → server-priced cart + `cart_token`.
2. `POST /api/checkout` with `Idempotency-Key` → `Checkout` record `PendingPayment`.
3. Gateway order created; customer pays.
4. Gateway webhook → signature verified → `payment.confirmed` written to outbox.
5. Consumer creates ERPNext `Sales Order` (submit) using prices from the checkout record, not the browser.
6. `Supplier Purchase Order` draft generated per supplier (grouped by supplier).
7. If amount ≤ threshold: auto-submit PO. Else: `AI Approval Request(SubmitPurchaseOrder)`.
8. Supplier fulfils; tracking captured; `Sales Order` updated; customer notified.
9. Delivery confirmed; reconciliation feeds W7.

**Failure paths**

| Failure | Behaviour |
|---|---|
| Payment succeeds, ERP fails | Outbox event retried with backoff; checkout stays `Paid`, order flag `ERP_PENDING`; founder sees it. **Never** double-charge or double-create |
| Webhook duplicate | Unique `event_id` → `200`, no state change |
| Webhook amount mismatch | Rejected + alert; payment investigated before order creation |
| Supplier stock gone at order time | Checkout blocked at validation; if after payment → auto-refund path with approval |
| Supplier mapping missing | Order held; not created against a guessed supplier |
| PO submit fails | Approval request or retry; Sales Order remains valid |
| Customer cancels after payment, before PO | Refund flow W6; PO cancelled or never submitted |

**Invariants**

- One `Idempotency-Key` → at most one `Sales Order`.
- No `Sales Order` exists without a verified payment event.
- No `Purchase Order` is submitted without an approval record above threshold.
- The browser's price is never used to create a financial document.

---

## W6 — REFUND

**Trigger:** customer request via ticket, or supplier failure.

**Happy path**

1. Verify order + payment exist and are within policy window.
2. Eligibility check: delivered? return received? supplier fault?
3. AI prepares recommendation with evidence → `AI Approval Request(IssueRefund)`.
4. Founder approves (all refunds in Phase 5; auto-approve may be introduced later under a hard cap, via ADR).
5. Gateway refund executed; reference recorded.
6. ERPNext credit note + refund payment entry.
7. Customer notified.
8. Reconciliation: refund appears in both gateway and ERP; no orphan.

**Failure paths:** gateway refund fails → retry job, order stays `RefundPending`, never marked `Refunded`. ERP fails after gateway success → outbox retry, visible exception.

**Invariants:** no refund without an approval record; refund amount ≤ captured amount; every refund has a gateway reference and an ERP document.

---

## W7 — DAILY FINANCIAL RECONCILIATION

**Trigger:** scheduled, daily after settlement window.

**Steps:** pull gateway settlement report → compare with `Payment Entry` → pull affiliate report → reconcile → compute contribution profit per order → detect anomalies (paid-but-no-order, order-but-no-payment, refund-without-credit-note, commission-paid-without-conversion).

**Output:** `Reconciliation Report` + exceptions on the dashboard.

**Invariant:** the report never edits a transaction. It only reports and queues corrections.

---

## W8 — SUPPLIER MONITORING

**Trigger:** scheduled (daily) + on-order.

**Steps:** read supplier stock feed → diff against `supplier_stock` → update `last_stock_sync` → if quantity hits 0 → `status = Out of Stock`, hide from catalog → alert if a published product goes out of stock while orders are open.

**Invariant:** stock sync never modifies `selling_price` or `supplier_cost` without approval.

---

## W9 — AI TASK LIFECYCLE

**Trigger:** any workflow needing inference.

**Steps:** enqueue `AI Task(Queued)` → worker takes oldest → `Running` with timeout → validate output → `Succeeded` or `Failed` → retry per policy → exhaustion → `Rejected` + exception surfaced.

**Rules:** one concurrent inference on this hardware (ADR-0004). A stuck task is requeued after 10 minutes without heartbeat.

**Invariant:** an AI failure never rolls back or blocks a business transaction. The transaction completes; the AI enrichment is retried or dropped.

---

## W10 — APPROVAL GATE

**Trigger:** any action above threshold or in the high-risk list.

**Blocked without approval:** publish product · submit PO · issue refund · change selling price · onboard supplier · bulk content publish · change payment mode.

**Flow:** action proposed → `AI Approval Request(Pending)` with rationale and financial impact → founder approves/rejects with a note → action executes or is discarded → audit record retained even if rejected.

**Invariant:** no agent may set `approval_status`. Enforced by role, not by convention.

---

## W11 — BACKUP AND RESTORE

**Trigger:** daily scheduled.

**Steps:** `bench backup --with-files` → checksum → copy to secondary location → log. Monthly: restore into a scratch site, run smoke tests, record duration.

**Invariant:** a restore that has not been executed is not a backup. Restoration evidence is a phase gate.

---

## CROSS-CUTTING FAILURE POLICIES

| Situation | Policy |
|---|---|
| External service down | Retry with exponential backoff, cap 5, then dead-letter + alert. Never block the customer path |
| Partial write | Forbidden by transaction + outbox design. If observed, it is a defect |
| Duplicate delivery | Expected. All consumers idempotent |
| Clock skew | Webhooks tolerate ±300 s. Business dates use server time |
| Data inconsistency | Report, do not auto-correct. Corrections are explicit and audited |
| Agent misbehaviour | Disable the agent (`status = Disabled`), preserve its task history |
