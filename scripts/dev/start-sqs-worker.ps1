param()

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $repoRoot

Write-Host 'Starting local SQS worker...' -ForegroundColor Cyan
python scripts\dev\sqs_local_worker.py
