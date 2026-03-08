@echo off
cd /d "%~dp0"

echo Cleaning local API/frontend instances...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev\cleanup-local.ps1" -Targets all
if exist "%~dp0.dev-runtime\api-port.txt" del /q "%~dp0.dev-runtime\api-port.txt"
if exist "%~dp0.dev-runtime\web-port.txt" del /q "%~dp0.dev-runtime\web-port.txt"

echo Done.
