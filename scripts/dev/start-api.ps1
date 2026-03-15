param(
  [int[]]$PreferredPorts = @(8000, 8001, 8002),
  [int]$FallbackPortStart = 8003,
  [int]$FallbackPortEnd = 8100,
  [switch]$SkipCleanup
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $repoRoot

if (-not $SkipCleanup) {
  & (Join-Path $PSScriptRoot 'cleanup-local.ps1') -Targets api -Quiet
}

function Import-DotEnv([string]$Path) {
  if (-not (Test-Path $Path)) { return }
  Get-Content $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $idx = $line.IndexOf('=')
    if ($idx -lt 1) { return }
    $k = $line.Substring(0, $idx).Trim()
    $v = $line.Substring($idx + 1).Trim()
    [Environment]::SetEnvironmentVariable($k, $v, 'Process')
  }
}

function Test-PortFree([int]$Port) {
  $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
  return -not $listener
}

Import-DotEnv (Join-Path $repoRoot '.env')

# Local default: process tasks inline so Sources actions update immediately.
# Set LOCAL_USE_SQS=1 to keep queue URLs and force dispatch mode.
$localUseSqsRaw = ''
if ($env:LOCAL_USE_SQS) {
  $localUseSqsRaw = $env:LOCAL_USE_SQS
}
$useSqsLocal = ($localUseSqsRaw.Trim().ToLower() -in @('1', 'true', 'yes', 'on'))
if (-not $useSqsLocal) {
  [Environment]::SetEnvironmentVariable('SCRAPE_QUEUE_URL', $null, 'Process')
  [Environment]::SetEnvironmentVariable('ALERT_QUEUE_URL', $null, 'Process')
  [Environment]::SetEnvironmentVariable('LLM_QUEUE_URL', $null, 'Process')
}

if (-not $env:LLM_ENABLED) { $env:LLM_ENABLED = 'true' }
if (-not $env:AWS_REGION) { $env:AWS_REGION = 'eu-west-1' }
if (-not $env:BEDROCK_MODEL_ID) { $env:BEDROCK_MODEL_ID = 'anthropic.claude-3-haiku-20240307-v1:0' }

$port = $null
foreach ($candidate in $PreferredPorts) {
  if (Test-PortFree -Port $candidate) {
    $port = $candidate
    break
  }
}

if (-not $port) {
  for ($candidate = $FallbackPortStart; $candidate -le $FallbackPortEnd; $candidate++) {
    if (Test-PortFree -Port $candidate) {
      $port = $candidate
      break
    }
  }
}

if (-not $port) {
  throw "No free API port found in preferred or fallback range: $($PreferredPorts -join ', '), $FallbackPortStart-$FallbackPortEnd"
}

$runtimeDir = Join-Path $repoRoot '.dev-runtime'
if (-not (Test-Path $runtimeDir)) {
  New-Item -ItemType Directory -Path $runtimeDir | Out-Null
}
Set-Content -Path (Join-Path $runtimeDir 'api-port.txt') -Value $port -NoNewline

Write-Host "Starting API on http://localhost:$port" -ForegroundColor Cyan
Write-Host "LLM_ENABLED=$($env:LLM_ENABLED), AWS_REGION=$($env:AWS_REGION)" -ForegroundColor DarkCyan
if ($useSqsLocal) {
  Write-Host 'LOCAL_USE_SQS is enabled; queue dispatch mode is active.' -ForegroundColor DarkCyan
} else {
  Write-Host 'LOCAL_USE_SQS not set; running tasks inline for local dev.' -ForegroundColor Yellow
}

if ($env:SCRAPE_QUEUE_URL) {
  Write-Host 'SCRAPE_QUEUE_URL is set' -ForegroundColor DarkCyan
} else {
  Write-Host '[INFO] SCRAPE_QUEUE_URL not set; source triggers run inline locally.' -ForegroundColor DarkCyan
}

if ($env:LLM_QUEUE_URL) {
  Write-Host 'LLM_QUEUE_URL is set' -ForegroundColor DarkCyan
} else {
  Write-Host '[WARN] LLM_QUEUE_URL not set; /api/v1/llm/enrich/* may return 503.' -ForegroundColor Yellow
}

python -m uvicorn apps.api.main:app --reload --port $port
