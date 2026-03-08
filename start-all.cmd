@echo off
setlocal
cd /d "%~dp0"

set "STARTALL_FAILED=0"
set "API_WAIT_SECONDS=45"
set "WEB_WAIT_SECONDS=90"

echo.
echo ========================================
echo  Property Search - Start All
echo ========================================
echo.

echo [1/6] Cleaning existing local instances...
call "%~dp0stop-local.cmd"
if errorlevel 1 (
  echo [ERROR] Failed to stop local instances.
  exit /b 1
)

echo [2/6] Starting Docker services...
docker compose up -d
if errorlevel 1 (
  echo [ERROR] Failed to start docker compose services.
  exit /b 1
)

echo [3/6] Running database migrations...
python -m alembic upgrade head
if errorlevel 1 (
  echo [ERROR] Database migration failed.
  exit /b 1
)

echo [4/6] Seeding default sources...
python scripts\seed.py
if errorlevel 1 (
  echo [WARN] Seeding failed. Continuing startup.
)

echo [5/6] Starting API window...
start "PropertySearch API" cmd /k "cd /d %~dp0 && start-api-llm.cmd"

echo [6/6] Starting Web window...
start "PropertySearch Web" cmd /k "cd /d %~dp0web && start-dev.cmd"

echo.
set "API_PORT=8000"
set "WEB_PORT=3000"

powershell -NoProfile -Command "$p='%~dp0.dev-runtime\api-port.txt'; $deadline=(Get-Date).AddSeconds(12); while((Get-Date) -lt $deadline -and -not (Test-Path $p)){ Start-Sleep -Milliseconds 300 }"
powershell -NoProfile -Command "$p='%~dp0.dev-runtime\web-port.txt'; $deadline=(Get-Date).AddSeconds(20); while((Get-Date) -lt $deadline -and -not (Test-Path $p)){ Start-Sleep -Milliseconds 300 }"

if exist "%~dp0.dev-runtime\api-port.txt" set /p API_PORT=<"%~dp0.dev-runtime\api-port.txt"
if exist "%~dp0.dev-runtime\web-port.txt" set /p WEB_PORT=<"%~dp0.dev-runtime\web-port.txt"

echo [start-all] Target API port: %API_PORT%
echo [start-all] Target Web port: %WEB_PORT%

echo Waiting for API to become healthy (timeout: %API_WAIT_SECONDS%s)...
powershell -NoProfile -Command "$deadline=(Get-Date).AddSeconds(%API_WAIT_SECONDS%); $ok=$false; while((Get-Date) -lt $deadline){ try { $r=Invoke-RestMethod -Uri 'http://localhost:%API_PORT%/health' -TimeoutSec 3; if($r.status){ $ok=$true; break } } catch {}; Start-Sleep -Seconds 2 }; if($ok){ Write-Host '[start-all] API readiness: ok'; exit 0 } else { Write-Host '[start-all] API readiness: timeout'; exit 1 }"
if errorlevel 1 (
  echo [ERROR] API did not become healthy in time.
  set "STARTALL_FAILED=1"
)

echo Waiting for web to respond (timeout: %WEB_WAIT_SECONDS%s)...
powershell -NoProfile -Command "$deadline=(Get-Date).AddSeconds(%WEB_WAIT_SECONDS%); $ok=$false; while((Get-Date) -lt $deadline){ try { $res=Invoke-WebRequest -Uri 'http://localhost:%WEB_PORT%' -UseBasicParsing -TimeoutSec 4; if($res.StatusCode -ge 200 -and $res.StatusCode -lt 500){ $ok=$true; break } } catch {}; Start-Sleep -Seconds 2 }; if($ok){ Write-Host '[start-all] Web readiness: ok'; exit 0 } else { Write-Host '[start-all] Web readiness: timeout'; exit 1 }"
if errorlevel 1 (
  echo [WARN] Web did not respond in time. It may still be compiling in the spawned terminal.
)

echo.
echo Current runtime status:
call "%~dp0status-local.cmd"

echo.
echo ========================================
if "%STARTALL_FAILED%"=="1" (
  echo  Startup Completed With Errors
) else (
  echo  Startup Complete
)
echo ========================================
echo API and Web are running in separate windows.
echo Run status-local.cmd anytime to re-check health.
echo.

if "%STARTALL_FAILED%"=="1" exit /b 1
