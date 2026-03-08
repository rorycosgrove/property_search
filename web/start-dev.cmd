@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\dev\cleanup-local.ps1" -Targets web -Quiet

if not exist ".dev-runtime" mkdir ".dev-runtime" >nul 2>&1

set "API_PORT=8000"
if exist ".dev-runtime\api-port.txt" (
	set /p API_PORT=<".dev-runtime\api-port.txt"
)
set "NEXT_PUBLIC_API_URL=http://localhost:%API_PORT%"

set "WEB_PORT="
for %%P in (3000 3001 3002) do (
	netstat -ano | findstr /R /C:":%%P .*LISTENING" >nul 2>&1
	if errorlevel 1 if not defined WEB_PORT set "WEB_PORT=%%P"
)
if not defined WEB_PORT set "WEB_PORT=3000"
echo %WEB_PORT%>".dev-runtime\web-port.txt"

cd /d "%~dp0"
if not exist "node_modules" (
	echo [ERROR] node_modules not found. Run: npm install
	exit /b 1
)

echo Starting web on http://localhost:%WEB_PORT%
echo NEXT_PUBLIC_API_URL=%NEXT_PUBLIC_API_URL%

if exist "node_modules\.bin\next.cmd" (
	call "node_modules\.bin\next.cmd" dev -p %WEB_PORT%
	if errorlevel 1 (
		echo [ERROR] next dev failed via local next.cmd.
		exit /b 1
	)
	exit /b 0
)

set "NPM_CMD=%ProgramFiles%\nodejs\npm.cmd"
if not exist "%NPM_CMD%" (
	set "NPM_CMD="
	for /f "delims=" %%I in ('where npm.cmd 2^>nul') do (
		if not defined NPM_CMD set "NPM_CMD=%%I"
	)
)
if not exist "%NPM_CMD%" (
	echo [ERROR] npm.cmd was not found in PATH. Install Node.js and ensure npm is available.
	exit /b 1
)

call "%NPM_CMD%" run dev -- -p %WEB_PORT%
if errorlevel 1 (
	echo [ERROR] Failed to start Next.js dev server using "%NPM_CMD%".
	exit /b 1
)
