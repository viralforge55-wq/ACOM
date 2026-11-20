# BACKUP AND RESTORE

**Status:** ⚠️ NOT YET IMPLEMENTED — Phase 0 stub
**Gate:** G8 — _Backup restored successfully_

---

## The rule

> A backup is not considered reliable until restoration has been successfully tested.

A backup that has never been restored is a file, not a recovery plan. Until this document contains observed restore timings from this machine, gate G8 is **open** and no phase may be declared complete.

---

## What will be backed up (Phase 1)

| Item | Includes | Sensitivity |
|---|---|---|
| Database | Full `mysqldump` of the site | High — contains customer/supplier data |
| Site files | `sites/<site>/public/files`, `private/files` | High |
| Configuration | Compose files, DocType fixtures, version pins | Low — **no secrets** |
| Secrets | `.env`, API keys | Never in a backup archive |

```bash
bench --site acom.localhost backup --with-files
```

---

## Restore runbook (to be completed with real output)

```bash
# 1. Fresh scratch site - never overwrite the source
bench new-site restore-test.localhost --admin-password <pw>

# 2. Restore
bench --site restore-test.localhost --force restore <db.sql.gz>
bench --site restore-test.localhost --force restore --with-public-files <files.tar>
bench --site restore-test.localhost --force restore --with-private-files <private-files.tar>

# 3. Migrate and smoke test
bench --site restore-test.localhost migrate
bench --site restore-test.localhost execute frappe.ping
```

### Recorded results

| Date | Source size | Restore duration | Smoke test | Verified by |
|---|---|---|---|---|
| _(none yet)_ | | | | |

---

## Known accepted risk (PoC only)

Backups will initially reside on the **same physical disk** as the database (C:). That protects against logical corruption and accidental deletion, not disk failure, theft, or OS reinstall.

This is an accepted risk for the local PoC and must be recorded as its own ADR before any real customer data exists. The mitigation, in preference order:

1. External drive (offline, rotated)
2. Second machine on the LAN
3. Encrypted cloud storage — only after confirming no PII leaves the country in violation of applicable rules

---

## Restore drill schedule

- **Every phase exit**: one restore into a scratch site.
- **Monthly**: full drill including site files.
- **Before any pricing or payment configuration change**: snapshot + restore test.

Drill script target: `infrastructure/backup/restore-drill.ps1` (not yet written).
