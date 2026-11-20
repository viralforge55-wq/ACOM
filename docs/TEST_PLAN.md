# TEST PLAN

**Status:** BINDING
**Principle:** a feature without execution evidence is not complete. "It should work" is a rejected claim.

---

## 1. TEST LAYERS

| Layer | Location | Runs against | Speed |
|---|---|---|---|
| Unit | `tests/unit/` | Pure Python / TS, no I/O | ms |
| Integration | `tests/integration/` | Real Frappe test site + MariaDB | seconds |
| Contract | `tests/integration/contract/` | API shape vs `API_CONTRACTS.md` | seconds |
| Security | `tests/security/` | Permissions, secrets, exposure | seconds |
| End-to-end | `tests/end-to-end/` | Full stack, Playwright + API | minutes |
| Restore drill | `tests/restore/` | Backup → fresh site → smoke | minutes |

**Fixture policy:** synthetic data only. No real customer, supplier, or payment data, ever. Payment gateways are mocked. Affiliate reports are generated fixtures.

---

## 2. MANDATORY TESTS BY AREA

### 2.1 Margin and scoring (unit — required for Phase 2)

| ID | Case | Expected |
|---|---|---|
| M1 | Standard product | Contribution profit matches hand-calculated value to the paisa |
| M2 | `selling_price = 0` | Validation error, no divide-by-zero |
| M3 | Negative contribution | `contribution_profit < 0`, publish blocked |
| M4 | GST present | Tax excluded from contribution profit |
| M5 | Return rate 0 vs 20% | Profit differs by exactly the expected return cost |
| M6 | Score bounds | Every weight applied; score clamped 0–100 |
| M7 | Missing supplier reliability | Score computed from available factors, flagged incomplete |

### 2.2 Idempotency (integration — gate G5)

| ID | Case | Expected |
|---|---|---|
| I1 | Same `Idempotency-Key`, same body, twice | One `Checkout`, second returns `200` with the same id |
| I2 | Same key, different body | `409 IDEMPOTENCY_CONFLICT`, no second record |
| I3 | Duplicate webhook `event_id` | `200`, `duplicate: true`, no second `Automation Event` |
| I4 | Concurrent identical requests (2 threads) | Exactly one record created |
| I5 | Duplicate affiliate conversion import | `skipped = 1`, no new row |

### 2.3 Payment safety (integration — gate G4, G5)

| ID | Case | Expected |
|---|---|---|
| P1 | Valid signature | Accepted, event written |
| P2 | Signature present but wrong | `400`, no state change |
| P3 | Signature header absent | `400` |
| P4 | Timestamp 301 s old | `WEBHOOK_STALE` |
| P5 | Replayed valid payload | `200`, no state change |
| P6 | Amount mismatch | `WEBHOOK_MISMATCH` + alert, no order |
| P7 | Currency mismatch | Rejected |
| P8 | Gateway success + ERP failure | Checkout `Paid`, order `ERP_PENDING`, retry queued, no duplicate SO |
| P9 | Frontend "success" without webhook | Order remains `PendingPayment` |

### 2.4 Price integrity (integration — gate G6)

| ID | Case | Expected |
|---|---|---|
| R1 | Client submits a lower price | `PRICE_MISMATCH` |
| R2 | Price changed after `cart_token` issued | `CART_EXPIRED` / mismatch |
| R3 | Client submits a currency | Ignored or rejected; never applied |
| R4 | Discount field injected | Rejected as unknown field |

### 2.5 Permissions (integration — gate G3)

| ID | Case | Expected |
|---|---|---|
| A1 | Guest reads `Affiliate Product` list API | Allowed, only public fields |
| A2 | Guest calls any mutating endpoint | `401` |
| A3 | Authenticated non-owner reads another order | `403` |
| A4 | Non-admin tries to set `approval_status` | `403` |
| A5 | Agent token calls refund endpoint | `403` |
| A6 | Public catalog response | Contains none of the banned fields (`DATA_DICTIONARY` §13) — asserted programmatically |

### 2.6 AI safety (integration — gate G7)

| ID | Case | Expected |
|---|---|---|
| X1 | Output fails schema | `Rejected`, `output_validated = 0` |
| X2 | Ollama timeout | `Timed Out`, retry per policy, business transaction unaffected |
| X3 | Output contains SQL or a shell command | Stored as text, never executed |
| X4 | Prompt-injection text in source content | Treated as data; no tool call follows |
| X5 | Exhausted retries | `Failed`, appears in founder exception queue |
| X6 | Attempt to submit a Purchase Order | Blocked by role, no submission |

### 2.7 ERPNext integrity (integration — Phase 1/2)

| ID | Case | Expected |
|---|---|---|
| E1 | Fresh site + `install-app acom_core` | Succeeds |
| E2 | `bench migrate` on empty site | Succeeds, zero errors |
| E3 | `bench migrate` twice | Idempotent |
| E4 | Restart containers | No data loss |
| E5 | Sales Order submit → PO draft created | Exactly one draft per supplier |
| E6 | Deleting a submitted document | Blocked |
| E7 | Custom field fixtures reinstall | No duplicates |

### 2.8 Affiliate (integration — Phase 4)

| ID | Case | Expected |
|---|---|---|
| F1 | Click recorded with sub-ID | `302` carries `click_id` |
| F2 | Click with no network | Rejected, product paused |
| F3 | Conversion import, first run | Rows inserted, `Pending` |
| F4 | Same import re-run | `skipped`, no change |
| F5 | Pending excluded from revenue | Dashboard total unchanged |
| F6 | Confirmation report | Status → `Confirmed`, revenue updates |
| F7 | Reversal | New row, original retained, revenue decreases |
| F8 | Orphan conversion | `Unmatched`, queued, not dropped |

### 2.9 End-to-end scenarios (Phase 9)

1. **Affiliate happy path** — discover → approve → publish → visit → click → import conversion → confirm → reconcile.
2. **Dropship happy path** — publish → add to cart → checkout → pay → SO → PO → ship → deliver → reconcile.
3. **Refund path** — request → approve → gateway refund → credit note → recon.
4. **Duplicate storm** — webhook delivered 10× concurrently → exactly one SO.
5. **Price tamper** — modified client cart → rejected.
6. **AI outage** — Ollama stopped mid-workflow → business flow completes, AI enrichment deferred.
7. **Restore** — backup → new site → smoke test passes.

---

## 3. PHASE GATES

| Phase | Must pass before exit |
|---|---|
| 0 | Env check reproducible · no secrets in Git · containers survive reboot |
| 1 | E1–E4 · Desk loads · SO and PO round-trip |
| 2 | M1–M7 · E1–E7 · A1–A6 |
| 3 | R1–R4 · catalog leak test · both CTA paths render |
| 4 | F1–F8 · reconciliation totals balance |
| 5 | I1–I5 · P1–P9 · refund flow |
| 6 | X1–X6 · one full agent task end-to-end |
| 7 | Flow success + failure paths · duplicate event handling |
| 8 | Dashboard numbers traceable to rows (drill-through) |
| 9 | All scenarios · restore drill · security gates G1–G9 |

---

## 4. RUNNING

```bash
# Backend
bench --site acom.localhost set-config allow_tests true
bench --site acom.localhost run-tests --app acom_core
bench --site acom.localhost run-tests --app acom_core --test test_margin

# Frontend
cd apps/storefront && npm test
cd apps/storefront && npx playwright test

# Environment + security
powershell -File scripts/check-env.ps1
powershell -File scripts/security-gates.ps1

# Restore drill
powershell -File infrastructure/backup/restore-drill.ps1
```

---

## 5. WHAT NOT TO TEST

- Frappe framework internals (trust the pinned version).
- Third-party gateway behaviour (mock it).
- CSS pixel output (visual review, not assertions).
- Generated marketing copy quality (human judgement, not an assertion).

---

## 6. REQUIRED COMPLETION EVIDENCE

Every task report must include exactly this block, filled with real output:

```
TASK: <one line>
SCOPE: <files changed>

COMMANDS RUN:
  <command>
  → <result summary>

TESTS:
  passed: N  failed: 0  skipped: 0
  new tests: <ids>

SECURITY CHECK:
  G1 DB/Redis not published      : PASS/FAIL
  G2 no secret in diff           : PASS/FAIL
  G3 guest cannot mutate         : PASS/FAIL
  (others as applicable)

KNOWN LIMITATIONS:
  <none, or honest list>

NOT DONE:
  <explicitly out of scope>
```

**Rejected evidence:** pasted code with no run output · "tests pass" without a count · screenshots of a terminal that does not show the failure cases · claims of completion with a skipped test unexplained.

---

## 7. FLAKY TEST POLICY

- A flaky test is a defect. Quarantine immediately with an issue reference.
- Do not re-run until green and call it passing.
- Time-dependent tests inject a clock; they never sleep.
