FROM python:3.12-slim

WORKDIR /app

# System deps (same as API — needed for geospatial libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgeos-dev \
    libproj-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

# Application code
COPY pyproject.toml ./
COPY packages/ packages/
COPY apps/ apps/
COPY scripts/ scripts/

# Python deps
RUN pip install --no-cache-dir .

# Default command (overridden in docker-compose per service)
CMD ["celery", "-A", "apps.worker.celery_app", "worker", "-l", "info"]
