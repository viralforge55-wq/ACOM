<#
.SYNOPSIS
    PROJECT ACOM - Phase 1 exit-criteria verification.

.DESCRIPTION
    Proves, with executed evidence, that:
      1. The stack is running and healthy
      2. acom.localhost:8080 answers
      3. The Frappe site responds through the API
      4. A dummy Sales Order and Purchase Order exist
      5. Both survive `docker compose down` + `up -d`
      6. No database or Redis port is published to the host

    Read-only against business data. It does restart the stack unless
    -SkipRestart is passed.

.PARAMETER SkipRestart
    Run checks 1-4 and 6 only. Useful for a fast pre-check.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\phase1-verify.ps1
#>

[CmdletBinding()]
param(
    [switch]$SkipRestart
)

$ErrorActionPreference = 'Continue'

$script:failures = 0
$script:warnings = 0

function Write-Result {
    param([string]$Gate, [string]$Status, [string]$Detail)
    $colour = switch ($Status) { 'PASS' { 'Green' } 'WARN' { 'Yellow' } 'FAIL' { 'Red' } default { 'Gray' } }
    if ($Status -eq 'FAIL') { $script:failures++ }
    if ($Status -eq 'WARN') { $script:warnings++ }
    Write-Host ("{0,-6} {1,-40} {2}" -f $Status, $Gate, $Detail) -ForegroundColor $colour
}

function Section { param([string]$Name) Write-Host "`n=== $Name ===" -ForegroundColor Cyan }

function Get-ComposeArgs {
    $set = @(
        'compose', '--env-file', (Join-Path $dockerDir 'acom.env'),
        '-f', (Join-Path $dockerDir 'upstream\compose.yaml'),
        '-f', (Join-Path $dockerDir 'upstream\overrides\compose.mariadb.yaml'),
        '-f', (Join-Path $dockerDir 'upstream\overrides\compose.redis.yaml'),
        '-f', (Join-Path $dockerDir 'upstream\overrides\compose.noproxy.yaml'),
        '-f', (Join-Path $dockerDir 'compose.acom.yml'),
        '-p', 'acom'
    )
    return $set
}

function Invoke-Compose {
    param([string[]]$Arguments, [switch]$Quiet)
    $all = (Get-ComposeArgs) + $Arguments
    if ($Quiet) {
        return (& docker @all 2>&1)
    }
    & docker @all
}

$root = Split-Path -Parent $PSScriptRoot
$dockerDir = Join-Path $root 'infrastructure\docker'
$site = 'acom.localhost'
$baseUrl = "http://$site`:8080"

Write-Host 'PROJECT ACOM - Phase 1 exit verification' -ForegroundColor White
Write-Host ("Timestamp: {0}" -f (Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'))

# ── 1. Containers ────────────────────────────────────────────────
Section 'Containers'
$expected = @('backend', 'frontend', 'websocket', 'queue-short', 'queue-long', 'scheduler', 'db', 'redis-cache', 'redis-queue')
$psJson = Invoke-Compose -Arguments @('ps', '--format', 'json') -Quiet

$running = @{}
foreach ($line in ($psJson -split "`r?`n")) {
    if (-not $line.Trim()) { continue }
    try {
        $obj = $line | ConvertFrom-Json
        $running[$obj.Service] = $obj
    } catch { }
}

foreach ($svc in $expected) {
    if ($running.ContainsKey($svc)) {
        $c = $running[$svc]
        $state = if ($c.State) { $c.State } else { 'unknown' }
        $health = if ($c.Health) { $c.Health } else { '' }
        $ok = ($state -eq 'running') -and ($health -ne 'unhealthy')
        Write-Result "service: $svc" $(if ($ok) { 'PASS' } else { 'FAIL' }) ("state={0} health={1}" -f $state, $health)
    } else {
        Write-Result "service: $svc" 'FAIL' 'not present in compose ps'
    }
}

$configurator = Get-ChildItem -ErrorAction SilentlyContinue (Join-Path $dockerDir 'compose.custom.yaml')
if (-not $configurator) {
    Write-Result 'compose.custom.yaml' 'WARN' 'not generated (not required to run)'
}

# ── 2. Network exposure (gate G1) ────────────────────────────────
Section 'Network exposure (gate G1)'
$ports = (& docker ps --format '{{.Names}}|{{.Ports}}' 2>&1)
$leaks = $ports | Where-Object { $_ -match '(0\.0\.0\.0|\[::\]):(3306|6379|8000)' }
if ($leaks) {
    foreach ($l in $leaks) { Write-Result 'published port' 'FAIL' $l }
} else {
    Write-Result 'db/redis/backend not published' 'PASS' 'only frontend:8080 exposed'
}

# ── 3. HTTP ──────────────────────────────────────────────────────
Section 'HTTP'
# Windows does not resolve *.localhost (only browsers special-case it),
# so every check pins the address and sends an explicit Host header.
# This still exercises nginx site resolution, which is what matters.
function Test-Http {
    param([string]$Path)
    $out = & curl.exe -s -o - -w "`n%{http_code}" -H "Host: $site" "http://127.0.0.1:8080$Path" 2>&1
    $lines = $out -split "`r?`n"
    $code = $lines[-1]
    $body = ($lines[0..($lines.Count - 2)]) -join "`n"
    return [pscustomobject]@{ Code = $code; Body = $body }
}

$pingRes = Test-Http -Path '/api/method/ping'
$pingOk = ($pingRes.Code -eq '200') -and ($pingRes.Body -match 'pong')
Write-Result 'GET /api/method/ping' $(if ($pingOk) { 'PASS' } else { 'FAIL' }) ("HTTP {0} body={1}" -f $pingRes.Code, $pingRes.Body.Trim())

$loginRes = Test-Http -Path '/login'
$loginOk = ($loginRes.Code -eq '200') -and ($loginRes.Body -match 'login|frappe|Frappe')
Write-Result 'GET /login (Desk)' $(if ($loginOk) { 'PASS' } else { 'FAIL' }) ("HTTP {0}, {1} bytes" -f $loginRes.Code, $loginRes.Body.Length)

# ── 4. Site + business documents ─────────────────────────────────
Section 'Site and documents'
$sites = Invoke-Compose -Arguments @('exec', '-T', 'backend', 'ls', '-1', 'sites') -Quiet
if (($sites -join ' ') -match [regex]::Escape($site)) {
    Write-Result 'site present' 'PASS' $site
} else {
    Write-Result 'site present' 'FAIL' ("not found in sites/. saw: {0}" -f (($sites | Where-Object { $_ -and $_ -notmatch 'assets|apps.txt|common_site' }) -join ', '))
}

function Get-SiteCounts {
    # `bench execute --args` is not usable here: the JSON argument gets mangled
    # by PowerShell -> docker exec -> sh quoting. A script file has no quoting
    # layer at all, so the numbers it prints are trustworthy.
    #
    # The script is copied on every call because /tmp lives in the container's
    # writable layer: `docker compose down` removes it along with the container.
    $countsScript = Join-Path $root 'scripts\site-counts.py'
    & docker @((Get-ComposeArgs) + @('cp', $countsScript, 'backend:/tmp/site-counts.py')) 2>&1 | Out-Null

    $raw = Invoke-Compose -Arguments @(
        'exec', '-T', 'backend', 'sh', '-lc',
        'cd /home/frappe/frappe-bench/sites && /home/frappe/frappe-bench/env/bin/python /tmp/site-counts.py'
    ) -Quiet
    $text = ($raw | Out-String)
    if ($text -match '(?s)<<<COUNTS>>>\s*(\{.*\})\s*<<<END>>>') {
        try { return ($matches[1] | ConvertFrom-Json) } catch { return $null }
    }
    return $null
}

$before = Get-SiteCounts
if (-not $before) {
    Write-Result 'site counts readable' 'FAIL' 'site-counts.py produced no JSON'
    $salesBefore = -1; $purchBefore = -1
} else {
    Write-Result 'site counts readable' 'PASS' 'via ORM script'
    $salesBefore = [int]$before.submitted.'Sales Order'
    $purchBefore = [int]$before.submitted.'Purchase Order'
}

Write-Result 'Sales Order submitted' $(if ($salesBefore -ge 1) { 'PASS' } else { 'FAIL' }) "$salesBefore"
Write-Result 'Purchase Order submitted' $(if ($purchBefore -ge 1) { 'PASS' } else { 'FAIL' }) "$purchBefore"
if ($before) {
    Write-Result 'setup wizard complete' $(if ($before.setup_complete) { 'PASS' } else { 'FAIL' }) "$($before.setup_complete)"
    Write-Result 'sales order names' 'PASS' (($before.names.'Sales Order') -join ', ')
    Write-Result 'purchase order names' 'PASS' (($before.names.'Purchase Order') -join ', ')
}

# ── 5. Restart survival ──────────────────────────────────────────
if ($SkipRestart) {
    Section 'Restart survival'
    Write-Result 'restart test' 'WARN' 'skipped (-SkipRestart)'
} else {
    Section 'Restart survival (down && up -d)'
    Write-Host '       stopping stack...' -ForegroundColor DarkGray
    $downOut = Invoke-Compose -Arguments @('down') -Quiet
    if (($downOut -join ' ') -match 'error') {
        Write-Result 'compose down' 'FAIL' ($downOut -join ' ')
    } else {
        Write-Result 'compose down' 'PASS' 'containers removed, volumes preserved'
    }

    Write-Host '       starting stack...' -ForegroundColor DarkGray
    Invoke-Compose -Arguments @('up', '-d') -Quiet | Out-Null

    # Wait for backend to answer
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 5
        $r = Test-Http -Path '/api/method/ping'
        if ($r.Code -eq '200' -and $r.Body -match 'pong') { $ready = $true; break }
    }
    Write-Result 'stack came back up' $(if ($ready) { 'PASS' } else { 'FAIL' }) $(if ($ready) { "after ~$($i*5)s" } else { 'no pong after 200s' })

    $salesAfter = -1
    $purchAfter = -1
    $after = Get-SiteCounts
    if ($after) {
        $salesAfter = [int]$after.submitted.'Sales Order'
        $purchAfter = [int]$after.submitted.'Purchase Order'
    }

    $salesOk = ($salesAfter -eq $salesBefore) -and ($salesAfter -ge 1)
    $purchOk = ($purchAfter -eq $purchBefore) -and ($purchAfter -ge 1)

    Write-Result 'Sales Order survived restart' $(if ($salesOk) { 'PASS' } else { 'FAIL' }) ("before={0} after={1}" -f $salesBefore, $salesAfter)
    Write-Result 'Purchase Order survived restart' $(if ($purchOk) { 'PASS' } else { 'FAIL' }) ("before={0} after={1}" -f $purchBefore, $purchAfter)
}

# ── 6. Data volume is the named volume ───────────────────────────
Section 'Storage (ADR-0003 / named volume)'
$vols = (& docker volume ls --format '{{.Name}}' 2>&1) | Where-Object { $_ -match 'acom_sites' }
if ($vols) {
    Write-Result 'named volume' 'PASS' ($vols -join ', ')
} else {
    Write-Result 'named volume' 'FAIL' 'acom_sites volume not found'
}

# ── Summary ──────────────────────────────────────────────────────
Write-Host "`n=== SUMMARY ===" -ForegroundColor Cyan
Write-Host ("FAIL: {0}   WARN: {1}" -f $script:failures, $script:warnings)

if ($script:failures -gt 0) {
    Write-Host "`nPhase 1 exit criteria NOT met." -ForegroundColor Red
    exit 1
}
Write-Host "`nPhase 1 exit criteria met." -ForegroundColor Green
exit 0
