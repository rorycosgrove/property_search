# Windows Local Development Setup

## Quick Start (Recommended)

### Option 1: All-In-One Startup
1. Open Command Prompt (cmd.exe)
2. Run:
   ```cmd
   cd d:\_code\property_search
   start-all.cmd
   ```
3. Verify status:
   ```cmd
   status-local.cmd
   ```

This path:
- cleans stale local API/frontend processes
- starts local Docker services
- runs migrations and seed step
- launches API, Web, and SQS worker in separate windows
- waits for readiness checks

### Option 2: Launch Split Windows (After Setup)

Use this when services are already prepared and you want separate API/Web windows quickly:

```cmd
cd d:\_code\property_search
start-local-services.cmd
status-local.cmd
```

If needed, you can launch only the queue consumer window:

```cmd
start-sqs-worker.cmd
```

### Option 3: Manual Setup

#### Terminal 1 - Setup & API
```cmd
cd d:\_code\property_search

REM Start PostgreSQL
docker compose up -d

REM Wait 5 seconds for PostgreSQL to start
timeout /t 5

REM Run migrations
python -m alembic upgrade head

REM Seed sources
python scripts\seed.py

REM Start API
start-api.cmd
```

#### Terminal 2 - Frontend
```cmd
cd d:\_code\property_search\web
start-dev.cmd
```

#### Access the Application
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Troubleshooting

### PowerShell npm Issues
If you see errors about npm.ps1 in PowerShell, use Command Prompt (cmd.exe) instead, or:

1. Run PowerShell as Administrator
2. Execute: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
3. Restart PowerShell

### Docker Not Running
Start Docker Desktop before running `start-all.cmd`.

### PostGIS Function Errors (`ST_Geography` / `ST_DWithin`)
If worker logs show spatial-function errors, enable PostGIS in your local DB:

```cmd
python -c "from packages.storage.database import engine; from sqlalchemy import text; c=engine.connect(); t=c.begin(); c.execute(text('CREATE EXTENSION IF NOT EXISTS postgis')); t.commit(); c.close(); print('postgis_ok')"
```

Then restart local services (`stop-local.cmd`, then `start-all.cmd`).

### `make` Command Not Found
On Windows shells without GNU Make, use direct commands:

```cmd
uv run pytest -q
uv run alembic upgrade head
docker compose up -d
```

### Port Already in Use
Use:

```cmd
stop-local.cmd
```

Then restart with `start-all.cmd`.

### Python Version Issues
Ensure Python 3.12+ is installed:
```cmd
python --version
```

### Missing Dependencies
Reinstall dependencies:
```cmd
pip install -e ".[dev]"
cd web && npm.cmd install
```

## Stopping the Application

1. Press `Ctrl+C` in both terminal windows
2. Stop PostgreSQL:
   ```cmd
   docker compose down
   ```

## Environment Variables

Create `.env` file in the root directory (copy from `.env.example` if available):
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/propertysearch
AWS_REGION=eu-west-1
LOG_LEVEL=INFO
```

## Next Steps

- View API documentation: http://localhost:8000/docs
- Check database: `docker exec -it ps_postgres psql -U postgres -d propertysearch`
- Run tests: `uv run pytest -q`
- Deploy to AWS: `python deploy.py`
