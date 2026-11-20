# DOCKER — PINNED STACK

**Status:** Phase 0 scaffold. No Compose file committed yet.

---

## Governing rules

1. **Use the official Frappe Docker repository as the baseline.** Do not author a Compose file from memory; an incomplete one will appear to work and then lose data or fail to migrate.
   `https://github.com/frappe/frappe_docker`
2. **No `latest` tags.** Every image is pinned to an explicit version.
3. **ACOM-specific configuration lives in an override file**, version-controlled here. Never edit the upstream Compose file in place.
4. MariaDB and Redis are **never** published to the host (security gate G1).
5. Data-root stays on **C:** (ADR-0003). Disk floor 25 GB.

---

## Layout (Phase 1 deliverable)

```
infrastructure/docker/
├── README.md                     this file
├── versions.env                  single source of truth for pins
├── compose.base.yml              vendored from frappe_docker, unmodified
├── compose.acom.yml              ACOM override (workers, volumes, limits)
└── docker-compose.override.local.yml   gitignored, machine-specific
```

---

## Version pinning record

Fill this in at Phase 1 and never change a row without an ADR entry.

| Component | Pin | Verified compatible | Date |
|---|---|---|---|
| Frappe | `version-15` → resolved tag | ☐ | |
| ERPNext | `version-15` → resolved tag | ☐ | |
| India Compliance | `version-15` → resolved tag | ☐ | |
| MariaDB | `10.6` | ☐ | |
| Redis | `6.2` | ☐ | |

**Resolution rule:** a branch name is not a pin. Record the resolved commit or image digest at the time of installation.

```bash
docker image inspect <image> --format '{{index .RepoDigests 0}}'
```

---

## Resource limits (ADR-0004)

On a 16 GB host with a 7 GB WSL allocation, an unbounded stack will OOM.

| Service group | CPU | Memory |
|---|---|---|
| `mariadb` | 2.0 | 1.5 GB |
| `redis-cache`, `redis-queue` | 0.5 each | 256 MB each |
| `backend` (gunicorn) | 2.0 | 1 GB |
| `worker-default`, `worker-short`, `worker-long` | 0.5 each | 512 MB each |
| `scheduler` | 0.25 | 256 MB |
| `frontend` (nginx) | 0.5 | 256 MB |
| `websocket` | 0.5 | 256 MB |

Set these in `compose.acom.yml` with `deploy.resources` or Compose v2 `mem_limit`/`cpus`. Verify with `docker stats` after boot; sum must stay under ~6 GB leaving room for the OS and Ollama.

**Reduce gunicorn workers** to 2 (default is higher) — this is the single biggest memory saving.

---

## Operational discipline

```bash
# Before any large build or image pull
docker system df

# Reclaim build cache and dangling images (safe)
docker system prune -f

# Also remove unused volumes (DESTROYS DATA — only on a disposable environment)
docker system prune --volumes -f
```

Run `docker system df` at the start of every phase. Report the number in the phase report.

---

## Boot verification

A stack is not "up" because `docker ps` shows containers. All of these must pass:

```bash
docker compose ps                      # all services healthy, not restarting
docker compose logs --tail=50 backend   # no traceback
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/method/ping   # 200
docker restart <all containers>        # then re-check data is present
```

Restart survival is a Phase 1 exit criterion.

---

## Not in scope

- Kubernetes (excluded by policy)
- Multiple ERP databases (excluded by policy)
- A second MariaDB for "AI data" (excluded by policy)
- Production TLS termination (local PoC only)
