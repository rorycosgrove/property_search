param(
  [ValidateSet('api', 'web', 'all')]
  [string]$Targets = 'all',
  [switch]$Quiet
)

$ErrorActionPreference = 'Continue'

function Write-Info([string]$Message) {
  if (-not $Quiet) {
    Write-Host $Message
  }
}

function Stop-ProcessSafe([int]$ProcessId) {
  if ($ProcessId -le 4) {
    return $false
  }

  try {
    Stop-Process -Id $ProcessId -Force -ErrorAction Stop
    Write-Info "[cleanup] stopped process $ProcessId"
    return $true
  } catch {
    Write-Info "[cleanup] skip process $ProcessId ($($_.Exception.Message))"
    return $false
  }
}

function Stop-ByPorts([int[]]$Ports) {
  foreach ($port in $Ports) {
    $conns = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq $port }
    if (-not $conns) {
      continue
    }

    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $pids) {
      [void](Stop-ProcessSafe -ProcessId $procId)
    }
  }
}

function Stop-ByCommandPattern([string[]]$Patterns) {
  $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue
  if (-not $procs) {
    return
  }

  foreach ($proc in $procs) {
    $cmd = [string]$proc.CommandLine
    if ([string]::IsNullOrWhiteSpace($cmd)) {
      continue
    }

    $matched = $false
    foreach ($pattern in $Patterns) {
      if ($cmd -like $pattern) {
        $matched = $true
        break
      }
    }

    if ($matched) {
      [void](Stop-ProcessSafe -ProcessId ([int]$proc.ProcessId))
    }
  }
}

$apiPorts = @(8000, 8001, 8002)
$webPorts = @(3000, 3001)
$apiPatterns = @(
  '*uvicorn*apps.api.main:app*',
  '*python*apps.api.main:app*'
)
$webPatterns = @(
  '*next dev*',
  '*node*next*dist*bin*next*'
)

switch ($Targets) {
  'api' {
    Write-Info '[cleanup] target: api'
    Stop-ByPorts -Ports $apiPorts
    Stop-ByCommandPattern -Patterns $apiPatterns
  }
  'web' {
    Write-Info '[cleanup] target: web'
    Stop-ByPorts -Ports $webPorts
    Stop-ByCommandPattern -Patterns $webPatterns
  }
  default {
    Write-Info '[cleanup] target: all'
    Stop-ByPorts -Ports ($apiPorts + $webPorts)
    Stop-ByCommandPattern -Patterns ($apiPatterns + $webPatterns)
  }
}

Write-Info '[cleanup] complete'
