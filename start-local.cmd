@echo off
REM Irish Property Research Dashboard - Local Development Startup
REM This script starts PostgreSQL, API, and Frontend

echo.
echo ========================================
echo  Irish Property Research Dashboard
echo  Local Development Startup
echo ========================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running. Please start Docker Desktop.
    pause
    exit /b 1
)

REM Start PostgreSQL
echo [1/4] Starting PostgreSQL...
docker compose up -d
if errorlevel 1 (
    echo [ERROR] Failed to start PostgreSQL
    pause
    exit /b 1
)

REM Wait for PostgreSQL to be ready
echo [2/4] Waiting for PostgreSQL to be ready...
timeout /t 5 /nobreak >nul

REM Run migrations
echo [3/4] Running database migrations...
python -m alembic upgrade head
if errorlevel 1 (
    echo [ERROR] Database migration failed
    pause
    exit /b 1
)

REM Seed sources if needed
echo [4/4] Seeding default sources...
python scripts\seed.py

echo.
echo ========================================
echo  Setup Complete!
echo ========================================
echo.
echo To start the application:
echo.
echo   1. API Server (in this window):
echo      python -m uvicorn apps.api.main:app --reload --port 8000
echo.
echo   2. Frontend (in a new window):
echo      cd web
echo      .\start-dev.cmd
echo.
echo   3. Open browser: http://localhost:3000
echo.
echo ========================================
echo.
pause
