param()

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$envPath = Join-Path $repoRoot '.env'
$runtimeDir = Join-Path $repoRoot '.dev-runtime'
$statusCachePath = Join-Path $runtimeDir 'queue-status-cache.json'

if (-not (Test-Path $envPath)) {
  Write-Host '[status] SQS: .env not found; skipping queue status.'
  exit 0
}

function Read-DotEnvValue([hashtable]$Map, [string]$Key) {
  if ($Map.ContainsKey($Key)) {
    return [string]$Map[$Key]
  }
  return ''
}

$vars = @{}
Get-Content $envPath | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith('#')) { return }
  $idx = $line.IndexOf('=')
  if ($idx -lt 1) { return }
  $k = $line.Substring(0, $idx).Trim()
  $v = $line.Substring($idx + 1).Trim()
  $vars[$k] = $v
}

$localUseSqsRaw = Read-DotEnvValue -Map $vars -Key 'LOCAL_USE_SQS'
$localUseSqs = $localUseSqsRaw.Trim().ToLower() -in @('1', 'true', 'yes', 'on')
if (-not $localUseSqs) {
  Write-Host '[status] SQS mode disabled (LOCAL_USE_SQS not truthy).'
  exit 0
}

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
  Write-Host '[status] SQS: aws CLI not found in PATH.'
  exit 0
}

$queues = @(
  @{ Name = 'scrape'; Url = (Read-DotEnvValue -Map $vars -Key 'SCRAPE_QUEUE_URL') },
  @{ Name = 'llm'; Url = (Read-DotEnvValue -Map $vars -Key 'LLM_QUEUE_URL') },
  @{ Name = 'alert'; Url = (Read-DotEnvValue -Map $vars -Key 'ALERT_QUEUE_URL') }
)

if (-not (Test-Path $runtimeDir)) {
  New-Item -ItemType Directory -Path $runtimeDir | Out-Null
}

$workerRunning = $false
try {
  $workerProc = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*sqs_local_worker.py*' }
  $workerRunning = $null -ne $workerProc
} catch {
  $workerRunning = $false
}

$previousVisible = @{}
if (Test-Path $statusCachePath) {
  try {
    $cached = Get-Content $statusCachePath -Raw | ConvertFrom-Json -AsHashtable
    if ($cached.ContainsKey('visible') -and $cached.visible -is [hashtable]) {
      $previousVisible = $cached.visible
    }
  } catch {
    $previousVisible = @{}
  }
}

$currentVisible = @{}
$growthWarnings = @()

foreach ($q in $queues) {
  if (-not $q.Url) {
    Write-Host ("[status] SQS {0}: missing queue URL" -f $q.Name)
    continue
  }

  try {
    $json = aws sqs get-queue-attributes `
      --queue-url $q.Url `
      --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible ApproximateNumberOfMessagesDelayed `
      --query Attributes `
      --output json

    $attrs = $json | ConvertFrom-Json
    $visible = [int]$attrs.ApproximateNumberOfMessages
    $currentVisible[$q.Name] = $visible

    if (-not $workerRunning -and $previousVisible.ContainsKey($q.Name)) {
      $prev = [int]$previousVisible[$q.Name]
      if ($visible -gt $prev) {
        $growthWarnings += ("{0} (+{1})" -f $q.Name, ($visible - $prev))
      }
    }

    Write-Host (
      "[status] SQS {0}: visible={1} in_flight={2} delayed={3}" -f `
        $q.Name, `
        $attrs.ApproximateNumberOfMessages, `
        $attrs.ApproximateNumberOfMessagesNotVisible, `
        $attrs.ApproximateNumberOfMessagesDelayed
    )
  } catch {
    Write-Host ("[status] SQS {0}: error querying queue ({1})" -f $q.Name, $_.Exception.Message)
  }
}

if (-not $workerRunning -and $growthWarnings.Count -gt 0) {
  Write-Host ("[status][WARN] SQS backlog increasing while worker is down: {0}" -f ($growthWarnings -join ', '))
}

try {
  $cacheObj = @{
    timestamp = (Get-Date).ToString('o')
    visible = $currentVisible
  }
  ($cacheObj | ConvertTo-Json -Depth 4) | Set-Content -Path $statusCachePath -Encoding UTF8
} catch {
  Write-Host '[status] SQS: unable to update queue status cache.'
}
