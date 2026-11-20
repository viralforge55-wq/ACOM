# ACOM Storefront (`apps/storefront`)

Next.js (App Router) + TypeScript + Tailwind CSS storefront for **PROJECT ACOM** (Phase 3 — Affiliate-first per ADR-0001).

## Architecture Boundaries

- Renders strictly from live `acom_core` APIs in ERPNext (`GET /api/catalog`, `GET /api/products/[slug]`, `GET /api/categories`, `POST /api/affiliate/click`, `GET /go/[click_id]`).
- Never connects to MariaDB or Redis directly (`docs/ARCHITECTURE_RULES.md` §1.2).
- Server-only ERPNext client (`src/lib/server/frappe_client.ts`) uses `node:http` to send an explicit `Host: acom.localhost` header to `http://127.0.0.1:8080` (WHATWG `fetch` silently strips `Host`, and Windows does not resolve `*.localhost` in Node).
- `AFFILIATE` and `DROPSHIP` actions are strictly separated (`ProductActionRouter` → `AffiliateActionCta` vs `DropshipActionPlaceholder`). Dropshipping checkout is deferred to Phase 5 per ADR-0001.

## Local Setup

```powershell
cd apps/storefront
copy .env.example .env.local
npm install
```

## Scripts

```powershell
npm run typecheck         # tsc --noEmit
npm run lint              # eslint . --max-warnings=0
npm run test:unit         # pure unit tests (formatting, banned-field guard, click schema)
npm run build             # production build
npm run start             # serves on http://127.0.0.1:3000
npm run test:integration  # live integration tests against :3000 + ERPNext :8080
```
