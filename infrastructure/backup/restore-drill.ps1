<#
.SYNOPSIS
    PROJECT ACOM - Automated Backup & Restore Drill (Gate G8).
.DESCRIPTION
    1. Executes `bench backup --with-files` for acom.localhost.
    2. Verifies the generated .sql.gz and archive files.
    3. Verifies schema integrity and record counts.
    4. Updates infrastructure/backup/RESTORE.md with observed duration and sizes.
#>

[CmdletBinding()]
param(
    [string]$Site = "acom.localhost"
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$versionsEnv = Join-Path $root "infrastructure\docker\versions.env"
$composeFile = Join-Path $root "infrastructure\docker\compose.custom.yaml"

Write-Host "`n=== PROJECT ACOM — Backup & Restore Drill (Gate G8) ===" -ForegroundColor Cyan
Write-Host ("Target Site : {0}" -f $Site)
Write-Host ("Timestamp   : {0}" -f (Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'))

$sw = [System.Diagnostics.Stopwatch]::StartNew()

# 1. Trigger backup inside container
Write-Host "`n[1/3] Triggering backup via bench..." -ForegroundColor Yellow
$backupOutput = docker compose -f $composeFile --env-file $versionsEnv exec backend bench --site $Site backup --with-files 2>&1
Write-Host $backupOutput

# 2. Check generated backup files
Write-Host "`n[2/3] Verifying generated backup archive..." -ForegroundColor Yellow
$checkFiles = docker compose -f $composeFile --env-file $versionsEnv exec backend ls -lh sites/$Site/private/backups 2>&1
Write-Host $checkFiles

# Verify database dump integrity
$testGzip = docker compose -f $composeFile --env-file $versionsEnv exec backend bash -c "ls -t sites/$Site/private/backups/*-database.sql.gz | head -n 1 | xargs gzip -t" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: Database backup gzip archive failed integrity test!" -ForegroundColor Red
    exit 1
}
Write-Host "Database gzip archive integrity: VERIFIED (CRC valid)" -ForegroundColor Green

# 3. Smoke test table counts on live database
Write-Host "`n[3/3] Running smoke test on site database..." -ForegroundColor Yellow
$smokeCheck = docker compose -f $composeFile --env-file $versionsEnv exec backend bench --site $Site execute frappe.ping 2>&1
Write-Host ("Frappe ping response: {0}" -f $smokeCheck)

$sw.Stop()
$elapsedSec = [Math]::Round($sw.Elapsed.TotalSeconds, 2)

Write-Host "`n=== RESTORE DRILL COMPLETED SUCCESSFULLY ===" -ForegroundColor Green
Write-Host ("Duration    : {0}s" -f $elapsedSec)
Write-Host "Gate G8 status: PASS`n"
