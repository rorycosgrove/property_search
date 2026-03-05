"""
AWS Lambda entry point for the FastAPI application.

Wraps the FastAPI app with Mangum to translate API Gateway events
into ASGI requests that FastAPI can process.
"""

from mangum import Mangum

from apps.api.main import app

handler = Mangum(app, lifespan="auto")
