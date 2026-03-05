"""
FastAPI application — Irish Property Research Dashboard API.

Provides REST endpoints for properties, analytics, alerts, sources,
saved searches, LLM enrichment, and system health.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from packages.shared.config import settings
from packages.shared.logging import setup_logging, get_logger

from apps.api.routers import (
    alerts,
    analytics,
    health,
    llm,
    properties,
    saved_searches,
    sold,
    sources,
)

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        f"http://localhost:{settings.api_port}",
    ],
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
