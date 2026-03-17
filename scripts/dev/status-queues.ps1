param()

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$envPath = Join-Path $repoRoot '.env'

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
