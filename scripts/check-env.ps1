<#
.SYNOPSIS
    PROJECT ACOM — environment verification.

.DESCRIPTION
    Reproduces the Phase 0 gate checks. Read-only: changes nothing.
    Exit code 0 = all gates pass, 1 = at least one FAIL.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\check-env.ps1
#>

$ErrorActionPreference = 'Continue'

$script:failures = 0
$script:warnings = 0

function Write-Result {
    param(
        [string]$Gate,
        [string]$Status,
        [string]$Detail
    )
    $colour = switch ($Status) {
        'PASS' { 'Green' }
        'WARN' { 'Yellow' }
        'FAIL' { 'Red' }
        default { 'Gray' }
    }
    if ($Status -eq 'FAIL') { $script:failures++ }
    if ($Status -eq 'WARN') { $script:warnings++ }

    $line = "{0,-6} {1,-38} {2}" -f $Status, $Gate, $Detail
    Write-Host $line -ForegroundColor $colour
}

function Section { param([string]$Name) Write-Host "`n=== $Name ===" -ForegroundColor Cyan }

Write-Host "PROJECT ACOM - environment verification" -ForegroundColor White
Write-Host ("Timestamp: {0}" -f (Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'))

# ── OS ───────────────────────────────────────────────────────────
Section 'Operating system'
$os = Get-CimInstance Win32_OperatingSystem
Write-Result 'OS' 'PASS' ("{0} build {1}" -f $os.Caption, $os.BuildNumber)

# ── CPU ──────────────────────────────────────────────────────────
Section 'CPU'
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
Write-Result 'CPU model' 'PASS' $cpu.Name.Trim()
Write-Result 'CPU cores' 'PASS' ("{0} physical / {1} logical" -f $cpu.NumberOfCores, $cpu.NumberOfLogicalProcessors)

# ── RAM ──────────────────────────────────────────────────────────
Section 'Memory'
$totalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$freeGB  = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
$ramStatus = if ($totalGB -ge 15) { 'PASS' } else { 'FAIL' }
Write-Result 'Total RAM' $ramStatus ("{0} GB" -f $totalGB)
$freeStatus = if ($freeGB -ge 8) { 'PASS' } elseif ($freeGB -ge 4) { 'WARN' } else { 'FAIL' }
Write-Result 'Free RAM at idle' $freeStatus ("{0} GB (ERPNext needs ~4 GB, Ollama ~3 GB)" -f $freeGB)

# ── DISK (ADR-0003: 25 GB floor on C:) ───────────────────────────
Section 'Disk'
$disk = Get-PSDrive -PSProvider FileSystem -Name C
$cFree = [math]::Round($disk.Free / 1GB, 1)
$diskStatus = if ($cFree -ge 25) { 'PASS' } elseif ($cFree -ge 15) { 'WARN' } else { 'FAIL' }
Write-Result 'C: free space' $diskStatus ("{0} GB (floor 25 GB - ADR-0003)" -f $cFree)

# ── VIRTUALIZATION ───────────────────────────────────────────────
Section 'Virtualization'
$hypervisor = (Get-CimInstance Win32_ComputerSystem).HypervisorPresent
Write-Result 'Hypervisor present' $(if ($hypervisor) { 'PASS' } else { 'FAIL' }) `
    'Hyper-V / VBS active means WSL2 virtualization is available'

# ── WSL2 ─────────────────────────────────────────────────────────
Section 'WSL2'
$wslExe = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wslExe) {
    Write-Result 'wsl.exe' 'FAIL' 'not found'
} else {
    $distros = (& wsl.exe --list --quiet 2>$null) -split "`r?`n" | Where-Object { $_.Trim() }
    if ($distros) {
        Write-Result 'Installed distros' 'PASS' ($distros -join ', ')
    } else {
        Write-Result 'Installed distros' 'FAIL' 'none found'
    }
}

$wslConfig = Join-Path $env:USERPROFILE '.wslconfig'
if (Test-Path $wslConfig) {
    $memoryLine = (Get-Content $wslConfig | Select-String -Pattern '^\s*memory\s*=').Line
    if ($memoryLine) {
        $memValue = ($memoryLine -split '=')[1].Trim()
        $memGB = [int](($memValue -replace '[^0-9]', ''))
        $status = if ($memGB -ge 6 -and $memGB -le 7) { 'PASS' } elseif ($memGB -gt 7) { 'WARN' } else { 'WARN' }
        $note = if ($memGB -gt 7) { 'above ADR-0004 ceiling; host may swap' } else { 'within ADR-0004 range (6-7 GB)' }
        Write-Result 'WSL memory allocation' $status ("{0} GB - {1}" -f $memGB, $note)
    } else {
        Write-Result 'WSL memory allocation' 'WARN' 'no memory= line in .wslconfig'
    }
} else {
    Write-Result '.wslconfig' 'WARN' 'absent - WSL will use host defaults'
}

# ── DOCKER ───────────────────────────────────────────────────────
Section 'Docker'
$dockerExe = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerExe) {
    Write-Result 'docker CLI' 'FAIL' 'not found'
} else {
    $dockerVersion = (& docker --version 2>&1) -join ' '
    Write-Result 'docker CLI' 'PASS' $dockerVersion

    $info = & docker info --format '{{.ServerVersion}}' 2>&1
    if ($LASTEXITCODE -eq 0 -and $info -notmatch 'failed') {
        Write-Result 'Docker daemon' 'PASS' ("server {0}" -f $info.Trim())
    } else {
        Write-Result 'Docker daemon' 'FAIL' 'not running - start Docker Desktop'
    }

    $compose = & docker compose version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Result 'docker compose' 'PASS' ($compose -join ' ')
    } else {
        Write-Result 'docker compose' 'WARN' 'not available'
    }
}

# ── TOOLCHAIN ────────────────────────────────────────────────────
Section 'Toolchain'
foreach ($tool in @(
    @{ Name = 'git';    Args = '--version' },
    @{ Name = 'node';   Args = '--version' },
    @{ Name = 'npm';    Args = '--version' },
    @{ Name = 'python'; Args = '--version' }
)) {
    $cmd = Get-Command $tool.Name -ErrorAction SilentlyContinue
    if ($cmd) {
        $version = (& $tool.Name $tool.Args 2>&1) -join ' '
        Write-Result $tool.Name 'PASS' $version.Trim()
    } else {
        Write-Result $tool.Name 'FAIL' 'not installed'
    }
}

# ── NETWORK EXPOSURE (security gate G1) ──────────────────────────
Section 'Network exposure (gate G1)'
$dockerReady = (Get-Command docker -ErrorAction SilentlyContinue) -and
               ((& docker info --format '{{.ServerVersion}}' 2>&1) -notmatch 'failed')

if (-not $dockerReady) {
    Write-Result 'Port exposure' 'WARN' 'skipped - Docker daemon not running'
} else {
    $exposed = & docker ps --format '{{.Names}}|{{.Ports}}' 2>$null |
        Where-Object { $_ -match '(0\.0\.0\.0|\[::\]):(3306|6379)' }

    if ($exposed) {
        foreach ($line in $exposed) { Write-Result 'DB/Redis exposure' 'FAIL' $line }
    } else {
        Write-Result 'DB/Redis exposure' 'PASS' 'no 3306/6379 published to 0.0.0.0'
    }
}

# ── SECRETS (security gate G2) ───────────────────────────────────
Section 'Repository hygiene (gate G2)'
$repoRoot = Split-Path -Parent $PSScriptRoot
if (Test-Path (Join-Path $repoRoot '.git')) {
    $tracked = & git -C $repoRoot ls-files 2>$null
    $leaks = $tracked | Where-Object { $_ -match '(^|/)\.env$|\.pem$|\.key$|site_config\.json$' }
    if ($leaks) {
        foreach ($l in $leaks) { Write-Result 'Secret committed' 'FAIL' $l }
    } else {
        Write-Result 'Tracked secrets' 'PASS' 'no .env / key / site_config tracked'
    }

    $dirty = & git -C $repoRoot status --porcelain 2>$null
    if ($dirty) {
        Write-Result 'Working tree' 'WARN' ("{0} uncommitted path(s)" -f ($dirty | Measure-Object).Count)
    } else {
        Write-Result 'Working tree' 'PASS' 'clean'
    }
} else {
    Write-Result 'Git repository' 'WARN' 'not initialised'
}

# ── SUMMARY ──────────────────────────────────────────────────────
Write-Host "`n=== SUMMARY ===" -ForegroundColor Cyan
Write-Host ("FAIL: {0}   WARN: {1}" -f $script:failures, $script:warnings)

if ($script:failures -gt 0) {
    Write-Host "`nPhase gate NOT met. Resolve FAIL items before proceeding." -ForegroundColor Red
    exit 1
}

Write-Host "`nAll blocking gates passed." -ForegroundColor Green
exit 0
