# ADR-0004 — AI Model Ceiling for a 16 GB / 4 GB-VRAM Host

- **Status:** Accepted
- **Date:** 2026-11-20
- **Deciders:** Founder / CEO
- **Amends:** `MASTER_BLUEPRINT` §10 (AI infrastructure), §15 (memory allocation)

## Context

Verified hardware:

| Resource | Value |
|---|---|
| RAM | 15.7 GB total, **~6.1 GB free at idle** (Windows consumes ~9.6 GB) |
| RAM upgrade | Not available — both SO-DIMM slots populated (2×8 GB) |
| GPU | RTX 2050, **4 GB VRAM** |
| CPU | i5-12450H, 8C/12T |
| WSL2 allocation | 6 GB (to become 7 GB) |

The ERPNext stack needs approximately 3.5–4 GB inside WSL (MariaDB, Redis ×2, gunicorn, workers, scheduler, nginx, socketio).

Approximate model footprints at Q4 quantization:

| Model class | Weights | Fits 4 GB VRAM? | Fits alongside ERPNext? |
|---|---|---|---|
| 1–1.5B | 0.8–1.1 GB | Yes, fully | Yes |
| **3B** | **~2.0 GB** | **Yes, fully** | **Yes** |
| 7–8B | 4.4–4.9 GB | No — partial offload | Marginal, slow |
| 14B+ | 8–9 GB+ | No | No |

The blueprint's §15 note ("do not run a large Ollama model simultaneously with the entire ERPNext stack") anticipated this but set an 8 GB WSL allocation, which on this host would force host-level swapping.

## Decision

1. **WSL2 memory: 7 GB** (not 8 GB), `processors=6`, `swap=4GB`.
2. **Default resident model: a 3B instruct model** (baseline `qwen2.5:3b-instruct`), fully GPU-resident.
3. **7B models are on-demand only** — never a default, never concurrent with a heavy ERP operation, and only for low-frequency, quality-sensitive drafting.
4. **`AI_MAX_CONCURRENT_TASKS=1`.** One inference at a time.
5. **Ollama runs on the host, not in Docker**, exposed on `127.0.0.1:11434` only. This avoids a second memory boundary and WSL GPU-passthrough configuration.
6. **No model is approved for production use until its licence is checked** for commercial use. This is a separate gate from capability.

Baseline assignment:

| Agent | Model class | Reason |
|---|---|---|
| Customer Support (classification) | 1.5–3B | Short, structured, latency-sensitive |
| Product Hunter (research JSON) | 3B, escalate to 7B | Schema-bound extraction |
| Listing & Content | 7B on-demand | Quality matters, runs rarely |
| Finance/Reconciliation | **No LLM** | Deterministic code only |
| BI / reporting summary | 3B | Natural-language wrapper over computed numbers |

## Consequences

**Positive**
- Inference stays on GPU; no swap thrash; ERPNext remains responsive.
- Lowest-capability model is used for the highest-frequency task, which is also the most structured.
- Finance logic is deterministic and testable, not probabilistic.

**Negative / accepted risks**
- 3B quality is materially below 7B/70B for open-ended reasoning. Mitigated by constraining every agent to a JSON schema with a validation gate, and by keeping the founder as approver.
- Product research quality will be limited; the Product Hunter is an *assistant*, and the blueprint already states the score is decision support, not proof.
- No concurrent AI work. A queue, not parallelism. Accepted.
- 7B responses may take 30–90 s on partial offload; acceptable for on-demand drafting, unacceptable for a customer-facing path.

## Explicitly rejected

| Option | Why rejected |
|---|---|
| 8 GB WSL allocation (blueprint default) | Host has ~6 GB free at idle; would swap on the Windows side |
| 14B+ local model | Does not fit; would require host RAM the machine does not have |
| Cloud LLM as the default | Violates §10 local-first and risks customer-data egress |
| Quantization below Q4 for the default | Quality loss exceeds the memory savings at 3B |

## Revisit criteria

- RAM upgraded to 32 GB or more → reconsider 7B resident, `AI_MAX_CONCURRENT_TASKS=2`.
- A GPU with ≥ 8 GB VRAM → 7B/8B resident becomes viable.
- Measured 3B failure rate on schema-valid tasks > 20% → escalate the default to 7B on-demand for that agent specifically.
