# Windows Local Development Setup

## Quick Start (Recommended)

### Option 1: Automated Setup
1. Open Command Prompt (cmd.exe) as Administrator
2. Run:
   ```cmd
   cd d:\_code\property_search
   start-local.cmd
   ```
3. Follow the on-screen instructions

### Option 2: Manual Setup

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
Start Docker Desktop before running the setup.

### Port Already in Use
If port 8000 or 3000 is in use:
- API: Change port in start-api.cmd
- Frontend: Edit web/start-dev.cmd and add `-p 3001`

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
- Run tests: `pytest`
- Deploy to AWS: `python deploy.py`
