"""
Application configuration via Pydantic Settings.

Reads from environment variables and .env file. All settings have sensible
defaults for development. Override via .env or environment for production.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the Property Search application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "propertysearch"
    postgres_user: str = "propertysearch"
    postgres_password: str = "changeme_in_production"

    # ── Redis ─────────────────────────────────────
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    # ── Celery ────────────────────────────────────
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # ── API ───────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    log_level: str = "INFO"

    # ── Frontend ──────────────────────────────────
    next_public_api_url: str = "http://localhost:8000"

    # ── LLM ───────────────────────────────────────
    llm_provider: str = "ollama"
    llm_enabled: bool = False

    # Ollama
    ollama_endpoint: str = "http://host.docker.internal:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout_seconds: int = 120

    # OpenAI / compatible (Claude, etc.)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_endpoint: str = "https://api.openai.com/v1"
    openai_timeout_seconds: int = 60

    # ── Scraping ──────────────────────────────────
    scrape_poll_interval_seconds: int = 900
    rss_poll_interval_seconds: int = 300
    ppr_poll_interval_seconds: int = 604800
    max_scrape_retries: int = 3
    request_timeout_seconds: int = 30
    scrape_delay_min_seconds: float = 2.0
    scrape_delay_max_seconds: float = 5.0
    user_agent: str = "PropertySearch/1.0 (+https://github.com/property-search)"

    # ── Geocoding ─────────────────────────────────
    geocoder_provider: str = "nominatim"
    geocoder_user_agent: str = "PropertySearch/1.0"
    geocoder_rate_limit: int = 1

    # ── Observability ─────────────────────────────
    enable_metrics: bool = True
    enable_tracing: bool = False

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
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


# Singleton — import this from anywhere
settings = Settings()


def get_settings() -> Settings:
    """Return the global Settings singleton."""
    return settings
