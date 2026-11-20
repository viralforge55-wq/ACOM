# ADR-0005 — Pin ERPNext v16, Not v15

- **Status:** Accepted (amended after first build attempt)
- **Date:** 2026-11-20
- **Deciders:** Founder / CEO
- **Amends:** Phase 0 `.env.example` assumption (`version-15`), `infrastructure/docker/README.md` pin table

## Context

Phase 0 documentation assumed `version-15` for Frappe, ERPNext, and India Compliance. That was an inference from the blueprint, not a blueprint requirement — `MASTER_BLUEPRINT` §1 only says "use a compatible, pinned set".

Evidence gathered from the official sources at Phase 1:

| Fact | Value |
|---|---|
| `frappe_docker` `example.env` default | `ERPNEXT_VERSION=v16.60.0` |
| `images/layered/Containerfile` default | `FRAPPE_BRANCH=version-16` |
| Build docs example `apps.json` | `version-16` |
| India Compliance active branches | `version-15`, `version-15-hotfix`, `version-16`, `version-16-hotfix` |
| India Compliance latest tag | `v16.9.1` (v16 line under active release) |
| ERPNext latest v16 tag | `v16.60.0` |
| Frappe latest v16 tag | `v16.60.2` |
| Debian base | `trixie` (v15 uses `bookworm`) |

India Compliance — the app the blueprint requires for GST — maintains a current v16 line. There is no compatibility reason to start a greenfield PoC on the older major.

## Decision

| Component | Pin |
|---|---|
| Frappe Framework | `version-16` branch via `frappe/build:version-16` |
| ERPNext | `v16.60.0` (release tag) |
| India Compliance | `v16.9.1` (release tag) |
| MariaDB | `mariadb:11.8` (upstream default) |
| Redis | `redis:8.6-alpine` (upstream default) |

## Correction: Frappe cannot be tag-pinned here

The first build attempt passed `FRAPPE_BRANCH=v16.60.2` and failed in under 10 seconds:

```
#5 [internal] load metadata for docker.io/frappe/build:v16.60.2
#5 ERROR: docker.io/frappe/build:v16.60.2: not found
```

`images/layered/Containerfile` uses `FRAPPE_BRANCH` for **two** purposes:

```dockerfile
FROM ${FRAPPE_IMAGE_PREFIX}/build:${FRAPPE_BRANCH}   # base image tag
...
bench init --frappe-branch=${FRAPPE_BRANCH}          # framework source branch
```

Base images are published per **branch** (`frappe/build:version-16`), never per release tag. Any value used must therefore exist as both an image tag and a git ref — and only branch names satisfy both.

**Consequence:** the Frappe Framework version is whatever `version-16` HEAD resolves to at build time. It is pinned by the *built image*, not by the build recipe. ERPNext and India Compliance remain genuinely tag-pinned through `apps.json`.

Resolved Frappe commit is recorded in `versions.env` after each build.

## Consequences

**Positive**
- Current upstream fixes and Debian base.
- India Compliance releases keep landing on v16; a v15 start would begin on a maintenance path.
- No divergence from upstream defaults, so upstream docs apply verbatim.
- ERPNext and India Compliance are reproducible by tag.

**Negative / accepted risks**
- **Frappe framework version floats with `version-16`.** A rebuild months from now can pull a different framework commit. Mitigated by: recording the resolved SHA, tagging the built image immutably, and — before any CI or multi-machine claim — switching to digest-pinned base images.
- `frappe/build:version-16` and `frappe/base:version-16` are floating tags. Same mitigation.
- v16 is newer and less battle-tested than v15. Mitigated by the Phase 1 exit gate (documents round-trip, migration succeeds, restart preserves data).
- Third-party Frappe apps written only for v15 will not work. None are planned.

## Revisit criteria

- India Compliance stops releasing on v16.
- A required third-party app is v15-only.
- A rebuild from `version-16` produces a materially different framework than the recorded SHA.
