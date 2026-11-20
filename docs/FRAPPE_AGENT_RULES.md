# FRAPPE AGENT RULES

**Status:** BINDING for all code written in `apps/acom_core`
**Target:** Frappe Framework v15 / ERPNext v15 (pinned in `infrastructure/docker/`)

These rules exist because a coding agent's most common failure on Frappe is not bad Python — it is violating framework invariants in a way that only surfaces during migration, upgrade, or a concurrent transaction.

---

## 1. THE SIX PROHIBITIONS

Never do these. No exceptions, no "just this once":

1. **Never edit ERPNext or Frappe source.** Both live in `apps/` inside the container image. If behaviour is wrong, override via `hooks.py`, a custom DocType, or a subclass in `acom_core`.
2. **Never run DDL against MariaDB directly.** No `ALTER TABLE`, `CREATE TABLE`, `DROP`, index creation by hand. Schema comes from DocType JSON + `bench migrate`.
3. **Never write to a DocType's table with raw SQL.** Use `frappe.get_doc(...).save()`, `frappe.db.set_value`, or `frappe.qb`.
4. **Never bypass `validate()` or `before_save()`** "because the data is trusted". If a validation blocks you, the validation is the specification.
5. **Never use `frappe.db.commit()` inside a controller or service.** Let the request boundary own the transaction. Manual commits break atomicity and produce partial states.
6. **Never add a dependency, patch, or `hooks.py` entry** that you cannot explain as necessary to the requested scope.

---

## 2. DOCUMENT LIFECYCLE

### 2.1 Controller methods — use the right one

| Hook | Use for | Example |
|---|---|---|
| `before_validate` | Defaults computed from other fields | set `selling_price` from price list |
| `validate` | Business rules, field consistency | reject negative margin |
| `before_insert` | Pre-save enrichment, ID generation | generate `click_id` |
| `on_submit` | Create dependent documents | Sales Order → draft Purchase Order |
| `on_cancel` | Reverse effects | cancel linked PO |
| `on_update` | Post-save side effects (non-critical) | enqueue analytics refresh |
| `after_commit` | External side effects | emit event, send webhook |

**Rules:**

- Put business logic in the controller or a service module — **not** in `hooks.py`, not in a `whitelist` function inline.
- A `validate()` must be idempotent and must not have side effects outside the document.
- Never enqueue a background job from `validate()`. Use `after_commit`.

### 2.2 Submittable documents

Only these are submittable (`is_submittable = 1`): none of the Phase 2 DocTypes. `Affiliate Product`, `Affiliate Click`, `Dropshipping Product`, `Supplier Performance`, `AI Task`, `AI Approval Request`, `Automation Event` are all **non-submittable**.

Order/cancel authority belongs to ERPNext documents (`Sales Order`, `Purchase Order`, `Sales Invoice`). Do not invent a parallel state machine.

### 2.3 Naming

- Transactional records use `naming_series`, defined in the DocType JSON, prefix declared in `docs/DATA_DICTIONARY.md`.
- Never call `frappe.model.naming.make_autoname()` ad hoc in a controller when `naming_series` is available.
- Slugs are derived once, on insert, and are immutable thereafter. Changing a slug requires a redirect record.

---

## 3. PERMISSIONS

- Every DocType ships with an explicit permissions block. The default (no permissions) is not acceptable.
- **Guest (`Guest` role): no permissions on any DocType.** Public catalog data is exposed only through whitelisted read APIs that select specific fields.
- `System Manager` gets full access. `All` gets read on reference data only (`Affiliate Product` published rows via API, not table access).
- Row-level restriction is done with `permission_query_conditions` in `hooks.py`, not in the UI.
- Any API that mutates money, orders, or approvals: `allow_guest=False`, and role-checked explicitly — a logged-in user is not automatically authorised.

```python
# Required shape for a mutating endpoint
@frappe.whitelist(methods=["POST"])
def approve_purchase_order(approval_request: str) -> dict:
    frappe.only_for(("System Manager", "ACOM Finance"))
    ...
```

---

## 4. TRANSACTIONS AND CONCURRENCY

- Frappe wraps a request in a transaction. Do not fight it.
- **Idempotency is database-enforced**, never memory-enforced:

```python
# Correct: unique index in DocType JSON on `idempotency_key`, then insert.
try:
    doc = frappe.get_doc({...}).insert()
except frappe.DuplicateEntryError:
    return existing_record(idempotency_key)
```

- Use `frappe.db.get_value(..., for_update=True)` when reading a row you are about to mutate (stock, approval state, payment state).
- Any operation that can be retried (webhook, job, import) must be safe to run twice and must record its attempt.
- Cross-document state changes go through the `Automation Event` outbox:

```
write business record  +  write Automation Event (same transaction)
        ↓
background worker consumes event → external effect → mark Completed / Failed / Dead Letter
```

Never perform an external HTTP call inside the same transaction as a business write.

---

## 5. BACKGROUND JOBS

- `frappe.enqueue(method, queue=..., timeout=..., job_id=...)`. Always set `timeout`. Always set `job_id` for deduplication.
- Queues: `short` (default, <60 s), `long` (AI tasks, imports), `default` (everything else). Do not add new queues.
- Job methods must be **idempotent** and must handle `frappe.db.rollback()` on their own failure path.
- Retry with backoff, and a hard cap. After the cap: status `Failed`, raise an `AI Approval Request` or an alert — never retry forever.
- Long jobs must heartbeat. A job silent for 10 minutes is considered dead and is requeued by the supervisor.

---

## 6. HOOKS

`hooks.py` is a manifest, not a place for logic.

```python
# Allowed
doc_events = {"Sales Order": {"on_submit": "acom_core.dropshipping_commerce.events.on_sales_order_submit"}}
scheduler_events = {"daily": ["acom_core.integration_management.tasks.reconcile_stale_events"]}
override_whitelisted_methods = {...}   # only with an ADR

# Forbidden
# any multi-line function body
# any business rule inline
# any wildcard doc_event like "*"
```

- No wildcard `doc_events`. They are unsearchable and cause cascade bugs.
- Every hook target must exist and be importable. A broken hook path prevents `bench migrate` from completing — verify by importing.

---

## 7. QUERIES

Prefer, in order:

1. `frappe.get_doc` / `frappe.get_all` / `frappe.get_list`
2. `frappe.qb` query builder
3. Parameterised `frappe.db.sql` — **only** in `analytics/`, with a comment justifying why the ORM was insufficient

```python
# Correct
frappe.qb.from_("Affiliate Click").select("count(*)").where(...)

# Forbidden
frappe.db.sql(f"select * from `tabAffiliate Click` where click_id = '{cid}'")
```

- Never `select *` in application code. Name the columns.
- Never build SQL with string interpolation. Ever.
- Every new query that scans a table needs a documented index in the DocType JSON (`search_index`, `unique`).

---

## 8. CUSTOM FIELDS AND SCHEMA CHANGES

- Prefer native DocType fields on `acom_core` DocTypes.
- If ERPNext documents genuinely need extra fields: **Custom Field fixtures**, exported to `apps/acom_core/acom_core/fixtures/custom_field.json`, loaded via `hooks.py` `fixtures`. Never hand-edited in the database.
- Property setters, client scripts, and print formats follow the same fixture rule.
- Never modify an ERPNext DocType's JSON in `apps/erpnext`. It will be lost on image update and may break migrations.

---

## 9. PATCHES AND MIGRATIONS

- Data migrations go in `patches.txt` with a version-gated `[pre_model_sync]` / `[post_model_sync]` entry and a matching function under `acom_core/patches/`.
- A patch must be: idempotent, logged, and safe to re-run after a partial failure.
- Never delete a patch entry after it has run in an environment. Supersede it with a new patch.
- `bench migrate` must complete on a **fresh site** (no pre-existing data) — this is a release gate, not a formality.

---

## 10. APIs

- All public-to-the-app endpoints live in `apps/acom_core/acom_core/api/`.
- Signature: typed, keyword-friendly, returns `dict`. No bare positional arguments in whitelisted methods.
- Validate every input explicitly. Frappe's type hints are documentation, not enforcement.
- Return `{ "ok": true, "data": {...} }` or raise `frappe.throw(..., exc=...)` with a machine-readable error code. Never return a string.
- Never leak a traceback to the caller. Log it; return a correlation ID.

Contract detail: `docs/API_CONTRACTS.md`.

---

## 11. TESTING FRAPPE CODE

```bash
bench --site acom.localhost set-config allow_tests true
bench --site acom.localhost run-tests --app acom_core
```

- Use `frappe.get_test_records` / `make_test_records` for reference data.
- Every test creates what it needs and cleans up in `tearDown`.
- Mock all outbound HTTP with `unittest.mock.patch` on the exact symbol used.
- Test the **failure** path for: duplicate idempotency key, invalid webhook signature, missing supplier mapping, AI schema violation, permission denial.
- A migration test means: `bench new-site` → `install-app acom_core` → `bench migrate` → assert DocType tables exist.

---

## 12. VERSION COMPATIBILITY

- Target: Frappe v15 / ERPNext v15. Do not use APIs introduced after the pinned tag.
- Before using an unfamiliar method, confirm it exists in the installed version:

```bash
bench --site acom.localhost execute frappe.utils.get_version
```

- No deprecated `frappe.model.document` patterns, no `frappe.utils.now()` where `now_datetime()` is correct, no `datetime.utcnow()` (timezone-naive) in business logic.
- All datetimes are timezone-aware and stored as site timezone (`Asia/Kolkata`).

---

## 13. WHAT "DONE" MEANS HERE

Before reporting completion, an agent must be able to show:

| Evidence | Command |
|---|---|
| App installs on a fresh site | `bench --site test.localhost install-app acom_core` |
| Migration succeeds | `bench --site test.localhost migrate` |
| Tests pass | `bench --site test.localhost run-tests --app acom_core` |
| Permissions enforced | A test asserting `PermissionError` for a non-privileged role |
| No raw SQL added | `grep -rn "frappe.db.sql" apps/acom_core` output reviewed |
| Hooks importable | `bench --site test.localhost console` then import each hook target |

No execution output → no completion claim.
