# ADR-0003 — Docker Data-Root Stays on C:

- **Status:** Accepted (supersedes the initial relocation recommendation)
- **Date:** 2026-11-20
- **Deciders:** Founder / CEO
- **Related:** `MASTER_BLUEPRINT` §15

## Context

Phase 0 environment verification on the ASUS Vivobook K3605ZF measured:

| Volume | Free at first check | Free after founder cleanup |
|---|---|---|
| C: | **16.6 GB** | **82.1 GB** |
| D: | 15.2 GB | 15.2 GB |
| E: | 61.3 GB | 61.3 GB |

Docker Desktop's data VHDX was already **14.27 GB** on C:.

The 16.6 GB figure was below the estimated requirement for the full stack:

| Component | Estimated |
|---|---|
| Frappe / ERPNext / India Compliance images | 3.5–5 GB |
| MariaDB data + site + assets | 1.5–3 GB |
| Node modules (storefront + app) | 1–2 GB |
| Ollama models (one 3B + one 7B) | 5–9 GB |
| WSL distro VHDX growth | 2–5 GB |
| **Total** | **13–24 GB** |

The initial recommendation was to relocate Docker's data-root to E: and set `OLLAMA_MODELS` there.

The founder cleaned C:, raising free space to 82.1 GB — **more than E: has free**.

## Decision

**Keep Docker's data-root and Ollama models on C: (default paths).**

Rationale:
1. C: now has the most free space of any volume.
2. Relocation adds risk: changing `data-root` on an existing Docker Desktop install can orphan images, and on Windows it interacts badly with the WSL-backed engine.
3. The OS drive is the fastest device on this machine; ERPNext's MariaDB benefits.
4. Fewer configuration deltas from a stock install = more reproducible environment.

**Disk floor:** if free space on C: falls below **25 GB**, stop and address it before the next phase. Enforced by `scripts/check-env.ps1`, which reports `FAIL` below that threshold.

## Consequences

**Positive**
- No custom `daemon.json`, no `DOCKER_DATA_ROOT`, no relocation runbook to maintain.
- Fastest storage for the database.
- One less Phase 0 task.

**Negative / accepted risks**
- C: is shared with the OS, page file, and user profile. A runaway Docker build can fill it and impair Windows.
- Backups live on the same physical disk as the data until an external target is chosen (recorded as a separate, accepted PoC risk).
- Mitigation: the 25 GB floor check, plus `docker system prune` discipline documented in `infrastructure/docker/README.md`.

## What changed versus the blueprint

Nothing architectural. The blueprint did not specify a data-root location; this ADR records the measurement and the decision so it is not re-litigated each phase.

## Revisit criteria

Re-evaluate if any of: C: free space < 25 GB persistently · WSL VHDX exceeds 40 GB · a second physical disk is added for data.
