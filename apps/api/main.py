"""
FastAPI application — Irish Property Research Dashboard API.

Provides REST endpoints for properties, analytics, alerts, sources,
saved searches, LLM enrichment, and system health.
Deployed on AWS Lambda via Mangum (API Gateway → Lambda → FastAPI)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routers import (
    admin,
    alerts,
    analytics,
    health,
    llm,
    properties,
    saved_searches,
    sold,
    sources,
)
from packages.shared.config import settings
from packages.shared.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    setup_logging(settings.log_level)
    logger.info("api_startup", host=settings.api_host, port=settings.api_port)
    yield
    logger.info("api_shutdown")


app = FastAPI(
    title="Irish Property Research Dashboard",
    description="API for researching properties to buy in Ireland",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────

# CORS origins — includes localhost for dev and configurable for Amplify domain
_cors_origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health.router, tags=["Health"])
app.include_router(properties.router, prefix="/api/v1/properties", tags=["Properties"])
app.include_router(sold.router, prefix="/api/v1/sold", tags=["Sold Properties"])
app.include_router(sources.router, prefix="/api/v1/sources", tags=["Sources"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alerts"])
app.include_router(saved_searches.router, prefix="/api/v1/saved-searches", tags=["Saved Searches"])
app.include_router(llm.router, prefix="/api/v1/llm", tags=["LLM / AI"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from fastapi import status

# Add global exception handler to always return CORS headers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    from fastapi.middleware.cors import CORSMiddleware
    # Default error response
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)}
    )
    # Add CORS headers
    origin = request.headers.get("origin")
    if origin and origin in _cors_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = _cors_origins[0] if _cors_origins else "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

# Add OPTIONS handler for all routes
@app.options("/{path:path}")
async def options_handler(path: str):
    response = JSONResponse(status_code=200, content={})
    from starlette.requests import Request
    import inspect
    origin = None
    # Try to get origin from request headers if possible
    frame = inspect.currentframe()
    while frame:
        if 'request' in frame.f_locals:
            req = frame.f_locals['request']
            origin = req.headers.get('origin')
            break
        frame = frame.f_back
    if origin and origin in _cors_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = _cors_origins[0] if _cors_origins else "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response
