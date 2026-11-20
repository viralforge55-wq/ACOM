# ADR-0002 — Defer Node-RED; Use Frappe Scheduler + Python Runner

- **Status:** Accepted
- **Date:** 2026-11-20
- **Deciders:** Founder / CEO
- **Amends:** `MASTER_BLUEPRINT` §6 (stack), §11 (automation), §20 Phase 7, §26 step 15

## Context

The blueprint selects Node-RED as the automation layer and specifies six flows plus HMAC-based endpoint security.

Existing capability already present in the chosen stack:

| Requirement | Frappe already provides |
|---|---|
| Scheduled triggers | `scheduler_events` (cron-like, in `hooks.py`) |
| Queue + workers | Redis queue, `frappe.enqueue`, worker pool |
| Retry with backoff | Custom, but trivial on top of the queue |
| Webhook ingestion | Whitelisted endpoints with access to raw body |
| HMAC verification | ~20 lines of Python, no extra runtime |
| Audit trail | `Automation Event` DocType |
| UI for state | Frappe Desk, already installed |
| Auth | Session / API key, already installed |

Node-RED would add: a second process, a second port, a second secret store, a second deployment unit, a second place where workflow state can live (Node-RED context), and a visual editor that is not needed by a single founder who is also directing a coding agent.

## Decision

**Defer Node-RED entirely.** Do not install it in Phase 7.

Implement the six flows as:

```
Frappe scheduler / webhook
   → acom_core service function
       → Python agent runner (ai/ or acom_core/ai_operations/)
           → Ollama
       → schema validation
       → business document write
       → Automation Event (outbox)
```

Retain `automation/node-red/`, `automation/workflows/`, and `automation/schemas/` in the repository. The JSON schemas are the contract; the flows are documented in `BUSINESS_WORKFLOWS.md` as behaviour, not as node graphs.

All security controls from §11 remain mandatory regardless of executor: HMAC-SHA256, timestamp window, replay rejection, schema validation, rate limiting, logging, retry.

## Consequences

**Positive**
- One less moving part on a 16 GB machine where every container competes for RAM.
- Workflow logic lives in version-controlled Python with tests, not in a JSON blob edited through a browser.
- Failures surface in `AI Task` / `Automation Event`, which the dashboard already reads.
- No second authentication surface.

**Negative / accepted risks**
- Flow visualisation is lost. Mitigated by `BUSINESS_WORKFLOWS.md` diagrams and structured logs.
- Non-developer editing of flows is not possible. Accepted: there is one founder, and they direct an agent.
- If the founder later wants visual flows, porting is a rewrite of glue code, not of business logic — the schemas and service functions are unchanged.

## Revisit criteria

Reconsider Node-RED only if **all** hold:
1. More than ~15 distinct flows exist.
2. A non-developer needs to modify flows without code review.
3. Host RAM ≥ 32 GB, or Node-RED runs on a separate machine.

## Compliance with blueprint

§2 forbids "unnecessary microservices" and requires "a small number of reliable technologies rather than introduce many overlapping systems". Node-RED as specified overlaps Frappe's scheduler, queue, auth, and audit. This ADR applies that principle.
