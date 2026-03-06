@echo off
echo Starting API Server on http://localhost:8000
echo Swagger docs: http://localhost:8000/docs
echo.
python -m uvicorn apps.api.main:app --reload --port 8000
