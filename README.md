# PROJECT ACOM

**AI-Driven Autonomous Commerce Company — Local-First, Open-Source, One-Person Business**

One founder. Multiple AI agents. One commerce operating system.

---

## Status

| Field | Value |
|---|---|
| Blueprint version | 2.0 (approved baseline) |
| Current stage | **Phase 0 — Foundation** |
| Repository state | Scaffolded, documentation-only |
| Deployment target | Local only (Windows 11 + WSL2 + Docker) |
| Production | **Out of scope** |

**Phase 0 exit criteria are not yet met.** No application code exists. Nothing is installed beyond host tooling.

---

## What This Is

ACOM is a commerce operating company with two independent revenue engines:

1. **Affiliate Commerce** — promote marketplace products, earn commission on referred sales. No inventory, no supplier payment, no fulfillment liability.
2. **Dropshipping Commerce** — sell through the ACOM storefront, purchase from an approved supplier, fulfil direct to the customer.

Both are supported by a **Product Discovery & Profitability Engine** that scores opportunities before any product is published.

Per **ADR-0001**, the affiliate engine is built first. It reaches real traffic and real commission data without a payment gateway, an idempotent checkout, or a rupee of working capital.

---

## Architecture at a Glance

```
┌────────────────────┐        ┌──────────────────────────────┐
│  Next.js Storefront│ ─────► │  Frappe / ERPNext (Docker)   │
│  TypeScript + TW   │ ◄───── │  ┌────────────────────────┐  │
└────────────────────┘  JSON  │  │ acom_core (custom app) │  │
                              │  ├────────────────────────┤  │
        ┌──────────────┐      │  │ ERPNext standard docs  │  │
        │ Ollama (LLM) │ ◄────┤  └────────────────────────┘  │
        │ on-demand    │      │  MariaDB · Redis · Workers   │
        └──────────────┘      └──────────────────────────────┘
```

- **ERPNext is the single system of record.** No second customer database, no second accounting engine.
- **AI agents never touch the database directly.** They call approved Frappe service methods and are gated by `AI Approval Request`.
- **`acom_core` is one app**, not six. Modularised by folder, not by deployment unit.

See `docs/ARCHITECTURE_RULES.md` for the binding rules.

---

## Repository Layout

```
D:\ACOM\
├── docs\                     # Governing documents — read before writing code
│   ├── MASTER_BLUEPRINT.md
│   ├── ARCHITECTURE_RULES.md
│   ├── FRAPPE_AGENT_RULES.md
│   ├── SECURITY_POLICY.md
│   ├── DATA_DICTIONARY.md
│   ├── API_CONTRACTS.md
│   ├── BUSINESS_WORKFLOWS.md
│   ├── TEST_PLAN.md
│   └── ADR\                  # Architectural decision records
├── infrastructure\
│   ├── docker\               # Pinned stack definition + overrides
│   ├── wsl\                  # WSL2 tuning
│   ├── backup\               # Backup + restore drills
│   └── local-config\         # Untracked local overrides
├── apps\
│   ├── acom_core\            # Frappe custom app (Phase 2)
│   └── storefront\           # Next.js storefront (Phase 3)
├── automation\               # Schemas retained; Node-RED deferred (ADR-0002)
├── ai\                       # Agent registry, prompts, JSON schemas, evals
├── integrations\             # affiliate / suppliers / payments / shipping
├── tests\                    # unit / integration / security / end-to-end
├── scripts\                  # Environment checks and operational helpers
├── .env.example
└── .gitignore
```

---

## Reading Order for Any Agent

1. `docs/MASTER_BLUEPRINT.md` — the business intent
2. `docs/ADR/` — what has been amended since, and why
3. `docs/ARCHITECTURE_RULES.md` — system boundaries and naming
4. `docs/FRAPPE_AGENT_RULES.md` — how to write Frappe code here
5. `docs/SECURITY_POLICY.md` — what is never allowed
6. `docs/API_CONTRACTS.md` — the interface you must not break
7. `docs/TEST_PLAN.md` — the evidence required before claiming completion

---

## Host Baseline (verified 2026-11-20)

| Resource | Value | Constraint |
|---|---|---|
| CPU | i5-12450H, 8C/12T | Adequate |
| RAM | 15.7 GB (2×8 GB, slots full) | **Binding limit** — WSL capped at 7 GB |
| GPU | RTX 2050, 4 GB VRAM | 3B models only, on-demand |
| Disk C: | 82.1 GB free | Healthy; alarm below 25 GB |
| WSL2 | Ubuntu-24.04, `.wslconfig` 6 GB / 4 CPU | Raise to 7 GB before Phase 1 |
| Docker | Desktop 29.6.2, Compose v5.3.1 | Daemon must start on boot |

Run `powershell -File scripts\check-env.ps1` to reproduce this table.

---

## First Milestone

> Find one profitable product, acquire one real customer, complete one successful
> transaction, deliver the product, reconcile the money, and prove positive
> contribution profit.

Not 10,000 products. Not 20 agents. Not a complicated dashboard.

---

## Licensing Note

ERPNext is **GPLv3**; Frappe Framework is **MIT**. Model licences vary and must be
checked per model for commercial use. Obtain legal advice before distributing
derivative software or offering a hosted commercial service.
