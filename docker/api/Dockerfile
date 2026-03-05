FROM python:3.12-slim

WORKDIR /app

# System deps
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
COPY alembic.ini ./
COPY alembic/ alembic/

# Python deps
RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
