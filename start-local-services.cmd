@echo off
setlocal
cd /d "%~dp0"

echo [local] Cleaning existing API/web instances...
call "%~dp0stop-local.cmd"

echo [local] Starting API window...
start "PropertySearch API" cmd /k "cd /d %~dp0 && start-api-llm.cmd"

echo [local] Starting Web window...
start "PropertySearch Web" cmd /k "cd /d %~dp0web && start-dev.cmd"

echo [local] Services launched in separate terminals.
echo [local] Run status-local.cmd to check health and ports.
