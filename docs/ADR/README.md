# ARCHITECTURAL DECISION RECORDS

An ADR is required **before** implementing any change to the approved architecture. It is not a retrospective note.

## Index

| ADR | Title | Status | Affects |
|---|---|---|---|
| [0001](0001-affiliate-engine-first.md) | Affiliate engine before dropshipping engine | Accepted | Blueprint §20, §26 |
| [0002](0002-defer-node-red.md) | Defer Node-RED; use Frappe scheduler + Python runner | Accepted | Blueprint §6, §11, §20, §26 |
| [0003](0003-docker-data-root-on-c.md) | Docker data-root stays on C: | Accepted | Blueprint §15 |
| [0004](0004-ai-model-ceiling.md) | AI model ceiling for 16 GB / 4 GB VRAM host | Accepted | Blueprint §10, §15 |

## When an ADR is required

- Adding, removing, or replacing a technology in the stack.
- Changing a system boundary or a data owner.
- Changing an API contract in a breaking way.
- Changing phase order or phase exit criteria.
- Accepting a known security or financial risk.
- Introducing a new background queue, service, or external dependency.
- Any decision a future agent could reasonably make differently.

## When it is not

- Implementing a rule that already exists in `ARCHITECTURE_RULES.md`.
- Fixing a bug within an established contract.
- Adding a field that the `DATA_DICTIONARY` already describes.

## Format

```markdown
# ADR-000N — Title

- Status: Proposed | Accepted | Superseded by ADR-000M | Rejected
- Date: YYYY-MM-DD
- Deciders: who
- Amends: which document/section

## Context
Facts, measurements, constraints. No opinion.

## Decision
One sentence, then specifics.

## Consequences
Positive / Negative / Neutral. Honest costs.

## Revisit criteria
The observable conditions under which this should be reopened.
```

## Rules

- One decision per ADR. Do not bundle.
- Numbers over adjectives: cite the measurement, not "it felt slow".
- Record the rejected options and why. That is the most valuable part later.
- Never delete an ADR. Supersede it and link both ways.
- An ADR without stated consequences is incomplete.
