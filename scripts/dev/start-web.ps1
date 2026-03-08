param(
  [int[]]$PreferredPorts = @(3000, 3001, 3002),
  [switch]$SkipCleanup
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$webRoot = Join-Path $repoRoot 'web'
Set-Location $repoRoot

if (-not $SkipCleanup) {
  & (Join-Path $PSScriptRoot 'cleanup-local.ps1') -Targets web -Quiet
}

function Test-PortFree([int]$Port) {
  $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
  return -not $listener
}

$runtimeDir = Join-Path $repoRoot '.dev-runtime'
if (-not (Test-Path $runtimeDir)) {
  New-Item -ItemType Directory -Path $runtimeDir | Out-Null
}

if (-not (Test-Path $webRoot)) {
  throw "Web root not found: $webRoot"
}
if (-not (Test-Path (Join-Path $webRoot 'package.json'))) {
  throw "Missing web/package.json"
}
if (-not (Test-Path (Join-Path $webRoot 'node_modules'))) {
  throw "Missing web/node_modules. Run: cd web; npm install"
}

$apiPortFile = Join-Path $runtimeDir 'api-port.txt'
$apiPort = 8000
if (Test-Path $apiPortFile) {
  $raw = (Get-Content $apiPortFile -Raw).Trim()
  if ($raw -match '^\d+$') {
    $apiPort = [int]$raw
  }
}

if (-not (Test-PortFree -Port $apiPort)) {
  for ($candidate = 8000; $candidate -le 8100; $candidate++) {
    if (-not (Test-PortFree -Port $candidate)) {
      try {
        $resp = Invoke-WebRequest -Uri "http://localhost:$candidate/health" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) {
          $apiPort = $candidate
          break
        }
      } catch {
        # ignore non-api listeners
      }
    }
  }
}

$webPort = $null
foreach ($candidate in $PreferredPorts) {
  if (Test-PortFree -Port $candidate) {
    $webPort = $candidate
    break
  }
}
if (-not $webPort) {
  throw "No free web port found in: $($PreferredPorts -join ', ')"
}

$env:NEXT_PUBLIC_API_URL = "http://localhost:$apiPort"
Set-Content -Path (Join-Path $runtimeDir 'web-port.txt') -Value $webPort -NoNewline

Write-Host "Starting web on http://localhost:$webPort" -ForegroundColor Cyan
Write-Host "NEXT_PUBLIC_API_URL=$($env:NEXT_PUBLIC_API_URL)" -ForegroundColor DarkCyan

Set-Location $webRoot
$nextCmd = Join-Path $webRoot 'node_modules/.bin/next.cmd'
if (Test-Path $nextCmd) {
  & $nextCmd dev -p $webPort
  if ($LASTEXITCODE -ne 0) {
    throw "next dev exited with code $LASTEXITCODE"
  }
  return
}

$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) {
  throw 'npm.cmd was not found in PATH and local next.cmd was not found'
}

& $npm.Source run dev -- -p $webPort
if ($LASTEXITCODE -ne 0) {
  throw "npm dev exited with code $LASTEXITCODE"
}
