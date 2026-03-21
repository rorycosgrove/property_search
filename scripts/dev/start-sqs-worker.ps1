param()

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $repoRoot

$restartDelaySeconds = 3
$restartCount = 0

Write-Host 'Starting local SQS worker supervisor...' -ForegroundColor Cyan
Write-Host ("Restart policy: always restart on exit after {0}s delay" -f $restartDelaySeconds)

if (Test-Path '.env') {
	$localUseSqsLine = Get-Content '.env' | Where-Object { $_ -match '^\s*LOCAL_USE_SQS\s*=' } | Select-Object -First 1
	if ($localUseSqsLine) {
		$value = ($localUseSqsLine -split '=', 2)[1].Trim().ToLower()
		if ($value -notin @('1', 'true', 'yes', 'on')) {
			Write-Host '[sqs-worker-supervisor] LOCAL_USE_SQS disabled in .env; not starting worker.' -ForegroundColor Yellow
			exit 0
		}
	}
}

while ($true) {
	$restartCount += 1
	Write-Host ("[sqs-worker-supervisor] launch #{0}" -f $restartCount) -ForegroundColor DarkCyan

	& python scripts\dev\sqs_local_worker.py
	$exitCode = $LASTEXITCODE

	if ($exitCode -eq 0) {
		Write-Host '[sqs-worker-supervisor] worker exited cleanly (code 0); restarting to keep consumer active.' -ForegroundColor Yellow
	} else {
		Write-Host ("[sqs-worker-supervisor] worker exited with code {0}; restarting." -f $exitCode) -ForegroundColor Yellow
	}

	Start-Sleep -Seconds $restartDelaySeconds
}
