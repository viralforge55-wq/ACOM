# ADR-0001 — Affiliate Engine Before Dropshipping Engine

- **Status:** Accepted
- **Date:** 2026-11-20
- **Deciders:** Founder / CEO
- **Amends:** `MASTER_BLUEPRINT` §20 (phase order), §26 (execution order)

## Context

Blueprint v2.0 sequences **Phase 4 = Dropshipping Transaction Engine** and **Phase 5 = Affiliate Engine**.

Blueprint §21 ("Business Launch Strategy") independently concludes that the company should **start with affiliate commerce**: no inventory investment, no supplier payment before customer purchase, no fulfilment responsibility, lower operational complexity, faster product-market validation.

These two directives contradict each other. Executing §20 as written means building the more expensive, higher-risk engine first, then validating demand with the cheaper one months later.

Cost comparison of the two engines:

| | Affiliate | Dropshipping |
|---|---|---|
| Payment gateway | Not required | Required (KYC, live keys, webhooks) |
| Idempotent checkout | Not required | Required |
| Supplier commitment | None | PO submission + approval gate |
| Refund handling | Network's problem | Ours |
| Revenue latency | Days after traffic | Weeks after build |
| Working capital | ₹0 | Supplier cost per order |
| Failure blast radius | Lost commission | Chargeback, unpaid supplier, angry customer |

## Decision

**Swap Phase 4 and Phase 5.** The Affiliate Engine ships first.

Revised order: 0 Foundation → 1 ERPNext PoC → 2 acom_core → 3 Storefront → **4 Affiliate** → **5 Dropshipping** → 6 AI → 7 Automation → 8 BI → 9 E2E.

## Consequences

**Positive**
- Real traffic, real clicks, and real commission data before a single rupee of working capital is committed.
- Payment-gateway and supplier-commitment risk is deferred until demand is evidenced.
- The storefront can launch with affiliate products only, which is a complete business.
- Affiliate reconciliation teaches the reconciliation patterns needed later for payments.

**Negative / accepted risks**
- Affiliate revenue per visitor is low; the business cannot be judged on it alone. Mitigated by treating Phase 4 as *validation*, not the end state.
- Phase 5 now starts later, so dropshipping revenue is delayed. Accepted: it is the riskier engine and should follow evidence.
- Dashboards built in Phase 8 will need affiliate metrics first, dropshipping second.

**Neutral**
- No technology changes. `acom_core` modules for both engines still ship in Phase 2.

## Compliance with blueprint

The blueprint's own §2 says "Start small, validate revenue, and expand only when justified" and §21 Stage A mandates affiliate-first. This ADR makes the roadmap consistent with those principles rather than overriding them.
