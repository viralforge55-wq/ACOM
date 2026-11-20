# WSL2 CONFIGURATION

**Target:** `%USERPROFILE%\.wslconfig`
**Governing ADR:** 0004 (7 GB ceiling on this 16 GB host)

---

## Rationale

| Setting | Value | Why |
|---|---|---|
| `memory` | 7 GB | ERPNext needs ~4 GB; 7 GB leaves headroom inside WSL without forcing the *Windows* side to swap. 8 GB was rejected — the host has ~6 GB free at idle. |
| `processors` | 6 | 12 logical cores; leaving 6 for Windows/GPU driver avoids input lag. |
| `swap` | 4 GB | Absorption buffer for MariaDB spikes. Not a substitute for RAM. |
| `localhostForwarding` | true | Lets the storefront reach ERPNext on `localhost:8000` without host-IP juggling. |
| `sparseVHD` | true | Prevents the VHDX from claiming disk it no longer uses. |

**Ollama runs on the host, not in WSL** (ADR-0004 §5). Its memory therefore does not come out of the 7 GB WSL budget — but it does compete for the same physical RAM. Do not run a 7B inference while a migration is running.

---

## The file

```ini
[wsl2]
memory=7GB
processors=6
swap=4GB
localhostForwarding=true

[experimental]
sparseVHD=true
```

Place it at `%USERPROFILE%\.wslconfig`, then:

```powershell
wsl --shutdown
```

WSL restarts on next use. Verify:

```powershell
wsl -d Ubuntu-24.04 -- free -h
wsl -d Ubuntu-24.04 -- nproc
```

Expected: ~7.0 Gi total memory, ~6 available, and 6 CPUs.

---

## Verification gates

| Check | Expected | Command |
|---|---|---|
| Memory respected | `total ≈ 7.0 Gi` | `wsl -d Ubuntu-24.04 -- free -h` |
| CPU count respected | `6` | `wsl -d Ubuntu-24.04 -- nproc` |
| Windows not swapping | commit charge < 90% | Task Manager → Performance → Memory |
| Docker engine healthy | server version printed | `docker info --format '{{.ServerVersion}}'` |
| Restart survival | data present after boot | `docker compose ps` + open a saved record |

`scripts/check-env.ps1` reads `.wslconfig` and flags an allocation above 7 GB as a warning.

---

## Known constraint

The host has 15.7 GB of RAM across two populated SO-DIMM slots. **There is no upgrade path without replacing both modules.** Every future capacity decision must be made against 16 GB, not against an assumed upgrade.

If memory pressure becomes routine:
1. Confirm the offender: `docker stats` vs Windows Task Manager.
2. Reduce gunicorn workers to 2 (biggest single win).
3. Lower Ollama concurrency to 1 (already set) and unload the model between runs (`OLLAMA_KEEP_ALIVE=0`).
4. Only then consider a 32 GB upgrade.
