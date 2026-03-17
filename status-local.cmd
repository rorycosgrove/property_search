@echo off
setlocal
cd /d "%~dp0"

set "API_PORT=unknown"
set "WEB_PORT=unknown"
if exist ".dev-runtime\api-port.txt" set /p API_PORT=<".dev-runtime\api-port.txt"
if exist ".dev-runtime\web-port.txt" set /p WEB_PORT=<".dev-runtime\web-port.txt"

echo [status] API_PORT=%API_PORT%
echo [status] WEB_PORT=%WEB_PORT%

if not "%API_PORT%"=="unknown" (
  powershell -NoProfile -Command "try { $api = Invoke-RestMethod -Uri 'http://localhost:%API_PORT%/health' -TimeoutSec 10; Write-Host ('[status] API status={0} db={1} version={2}' -f $api.status, $api.database, $api.version) } catch { Write-Host '[status] API health failed' }"
  powershell -NoProfile -Command "try { $llm = Invoke-RestMethod -Uri 'http://localhost:%API_PORT%/api/v1/llm/health' -TimeoutSec 10; Write-Host ('[status] LLM enabled={0} healthy={1} queue={2} ready={3} reason={4}' -f $llm.enabled, $llm.healthy, $llm.queue_configured, $llm.ready_for_enrichment, $llm.reason) } catch { Write-Host '[status] LLM health failed' }"
)

if not "%WEB_PORT%"=="unknown" (
  powershell -NoProfile -Command "try { $res = Invoke-WebRequest -Uri 'http://localhost:%WEB_PORT%' -UseBasicParsing -TimeoutSec 10; Write-Host ('[status] Web status_code={0}' -f $res.StatusCode) } catch { Write-Host '[status] Web health failed (check the PropertySearch Web window for npm/Next errors)' }"
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev\status-queues.ps1"
