# DOCKER — PINNED STACK

**Status:** Phase 2 active. Base ERPNext image built from upstream `frappe_docker`; `acom_core` layered cleanly via `Dockerfile.acom`.
**Baseline:** `frappe/frappe_docker` @ `5a7f074a2bc41dc7db352dc0a87ee4958e86e371` (2026-11-19)

---

## Governing rules

1. **Use the official Frappe Docker repository as the baseline.** Never author a Compose file from memory.
2. **No `latest` tags.** Every image is pinned.
3. **ACOM changes live in `compose.acom.yml`**, layered on the upstream files. Never edit upstream in place.
4. MariaDB and Redis are **never** published to the host (gate G1).
5. Data-root stays on **C:** (ADR-0003). Disk floor 25 GB.

---

## Files

| File | Tracked | Purpose |
|---|---|---|
| `versions.env` | yes | Single source of truth for pins |
| `apps.json` | yes | Custom app set for the base image build |
| `Dockerfile.acom` | yes | Layered image adding `apps/acom_core` on top of the base image |
| `compose.acom.yml` | yes | Memory/CPU limits (ADR-0004) |
| `acom.env.example` | yes | Compose env template |
| `acom.env` | **no** | Local secrets — gitignored |
| `compose.custom.yaml` | **no** | Generated resolved Compose — gitignored |
| `upstream/` | **no** | Vendored clone at the pinned commit |
| `build-image.log` | **no** | Build output |

Reproduce the baseline:

```powershell
git clone https://github.com/frappe/frappe_docker.git infrastructure/docker/upstream
git -C infrastructure/docker/upstream checkout 5a7f074a2bc41dc7db352dc0a87ee4958e86e371
```

---

## Pin table

| Component | Pin | Resolved | Verified |
|---|---|---|---|
| Frappe Docker | commit `5a7f074` | — | ☑ |
| Frappe Framework | `version-16` branch (**not** a tag) | _see `versions.env`_ | ☐ |
| ERPNext | `v16.60.0` tag | — | ☐ |
| India Compliance | `v16.9.1` tag | — | ☐ |
| MariaDB | `mariadb:11.8` | — | ☐ |
| Redis | `redis:8.6-alpine` | — | ☐ |
| Local image | `acom/erpnext:16.60.0-ic16.9.1` | — | ☐ |

### Why Frappe is branch-pinned

`images/layered/Containerfile` uses one argument for two purposes:

```dockerfile
FROM ${FRAPPE_IMAGE_PREFIX}/build:${FRAPPE_BRANCH}   # base image tag
bench init --frappe-branch=${FRAPPE_BRANCH}          # framework source
```

Base images exist only per branch. Passing a release tag fails immediately:

```
docker.io/frappe/build:v16.60.2: not found
```

So `FRAPPE_BRANCH` must be `version-16`. ERPNext and India Compliance remain tag-pinned via `apps.json`. See ADR-0005.

---

## Build

```powershell
cd infrastructure/docker/upstream
docker build `
  --build-arg FRAPPE_PATH=https://github.com/frappe/frappe `
  --build-arg FRAPPE_BRANCH=version-16 `
  "--secret=id=apps_json,src=D:\ACOM\infrastructure\docker\apps.json" `
  --tag acom/erpnext:16.60.0-ic16.9.1 `
  --file images/layered/Containerfile .
```

`apps.json` is passed as a **BuildKit secret**, not a build arg — build args are permanently visible in `docker image history`.

Expect 20–40 minutes. After it finishes, record the resolved SHAs:

```powershell
docker run --rm --entrypoint bash acom/erpnext:16.60.0-ic16.9.1 -c "cd /home/frappe/frappe-bench && for a in frappe erpnext india_compliance; do echo -n \"$a \"; cat apps/$a/../$a/__init__.py 2>/dev/null | head -1; done"
docker image inspect acom/erpnext:16.60.0-ic16.9.1 --format '{{index .RepoDigests 0}}'
```

App git history is stripped in the layered build (`find apps -path '*/.git' | xargs rm -fr`), so record the digest rather than a commit SHA.

---

## Run

```powershell
cd infrastructure/docker

docker compose --env-file acom.env `
  -f upstream/compose.yaml `
  -f upstream/overrides/compose.mariadb.yaml `
  -f upstream/overrides/compose.redis.yaml `
  -f upstream/overrides/compose.noproxy.yaml `
  -f compose.acom.yml `
  -p acom config > compose.custom.yaml

docker compose -p acom -f compose.custom.yaml up -d
```

### Exposed surface

| Service | Port | Reachable |
|---|---|---|
| `frontend` (nginx) | `8080` | `http://acom.localhost:8080` |
| `backend` | 8000 | **internal only** |
| `db` (MariaDB) | 3306 | **internal only** |
| `redis-cache`, `redis-queue` | 6379 | **internal only** |

### Storage

`sites` is a **named Docker volume** (`compose.yaml` line 103), not a Windows bind mount. That is deliberate: a bind mount of `D:\` into Linux makes Frappe and MariaDB file I/O 5–10× slower and produces permission errors.

Backups therefore export through `bench backup`, not through the filesystem:

```powershell
docker compose -p acom exec backend bench --site acom.localhost backup --with-files
docker compose -p acom cp backend:/home/frappe/frappe-bench/sites/acom.localhost/private/backups/. .\backups\
```

---

## Create the site

Wait for `configurator` to exit and `db` to be healthy before this.

```powershell
docker compose -p acom exec backend bench new-site acom.localhost `
  --mariadb-user-host-login-scope='172.%.%.%' `
  --db-root-password <DB_PASSWORD from acom.env> `
  --admin-password <choose locally> `
  --install-app erpnext
```

Then verify India Compliance is present and installable:

```powershell
docker compose -p acom exec backend bench --site acom.localhost install-app india_compliance
```

---

## Operational discipline

```powershell
docker system df                 # run at the start of every phase
docker system prune -f           # safe: build cache + dangling images
docker system prune --volumes -f # DESTROYS DATA — disposable environments only
```

---

## Boot verification

A stack is not "up" because `docker ps` shows containers.

```powershell
docker compose -p acom ps                                   # healthy, not restarting
docker compose -p acom logs --tail=50 backend               # no traceback
curl.exe -s -o NUL -w "%{http_code}" http://acom.localhost:8080/api/method/ping   # 200
docker compose -p acom restart                              # then confirm data survives
```

Restart survival is a Phase 1 exit criterion.

---

## Not in scope

- Kubernetes (excluded by policy)
- Multiple ERP databases (excluded by policy)
- Production TLS termination
- Publishing the backend or database port
