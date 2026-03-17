"""
Application configuration via Pydantic Settings.

Reads from environment variables and .env file. All settings have sensible
defaults for development. Override via .env or environment for production.
"""

from __future__ import annotations

import json
import os

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.shared.constants import (
    DEFAULT_PPR_INTERVAL_SECONDS,
    DEFAULT_RSS_INTERVAL_SECONDS,
    DEFAULT_SCRAPE_INTERVAL_SECONDS,
    GEOCODER_RATE_LIMIT_SECONDS,
    MAX_SCRAPE_RETRIES,
    REQUEST_TIMEOUT_SECONDS,
    SCRAPE_DELAY_MAX_SECONDS,
    SCRAPE_DELAY_MIN_SECONDS,
)


class Settings(BaseSettings):
    """Central configuration for the Property Search application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database (RDS PostgreSQL) ─────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "propertysearch"
    postgres_user: str = "propertysearch"
    postgres_password: str = "changeme_in_production"

    # ── AWS ───────────────────────────────────────
    aws_region: str = "eu-west-1"
    aws_profile: str = ""
    aws_secrets_arn: str = ""

    # ── SQS Queue URLs ────────────────────────────
    scrape_queue_url: str = ""
    llm_queue_url: str = ""
    alert_queue_url: str = ""

    # ── DynamoDB (config cache) ───────────────────
    dynamodb_config_table: str = "property-search-config"

    # ── API ───────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # ── Frontend ──────────────────────────────────
    next_public_api_url: str = "http://localhost:8000"

    # ── LLM (Amazon Bedrock) ─────────────────────
    llm_provider: str = "bedrock"
    llm_enabled: bool = False
    bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_inference_profile_id: str = ""
    bedrock_max_tokens: int = 4096

    # ── Scraping ──────────────────────────────────
    scrape_poll_interval_seconds: int = DEFAULT_SCRAPE_INTERVAL_SECONDS
    rss_poll_interval_seconds: int = DEFAULT_RSS_INTERVAL_SECONDS
    ppr_poll_interval_seconds: int = DEFAULT_PPR_INTERVAL_SECONDS
    max_scrape_retries: int = MAX_SCRAPE_RETRIES
    request_timeout_seconds: int = REQUEST_TIMEOUT_SECONDS
    scrape_delay_min_seconds: float = SCRAPE_DELAY_MIN_SECONDS
    scrape_delay_max_seconds: float = SCRAPE_DELAY_MAX_SECONDS
    user_agent: str = "PropertySearch/1.0 (+https://github.com/property-search)"

    # ── Geocoding ─────────────────────────────────
    geocoder_provider: str = "nominatim"
    geocoder_user_agent: str = "PropertySearch/1.0"
    geocoder_rate_limit: float = GEOCODER_RATE_LIMIT_SECONDS

    # ── Observability ─────────────────────────────
    enable_metrics: bool = True
    enable_tracing: bool = False
    backend_log_retention_days: int = 7

    @model_validator(mode="after")
    def _resolve_secrets(self) -> Settings:
        """Fetch DB credentials from Secrets Manager when running in Lambda."""
        if self.aws_secrets_arn and os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            import boto3

            client = boto3.client("secretsmanager", region_name=self.aws_region)
            resp = client.get_secret_value(SecretId=self.aws_secrets_arn)
            secret = json.loads(resp["SecretString"])
            self.postgres_user = secret["username"]
            self.postgres_password = secret["password"]
        return self

    # ── Derived properties ────────────────────────
    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_lambda(self) -> bool:
        """Detect if running inside AWS Lambda."""
        import os
        return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


# Singleton — import this from anywhere
settings = Settings()


def get_settings() -> Settings:
    """Return the global Settings singleton."""
    return settings
