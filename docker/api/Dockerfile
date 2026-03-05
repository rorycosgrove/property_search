FROM public.ecr.aws/lambda/python:3.12

# System deps for PostGIS / GDAL
RUN dnf install -y \
    gcc \
    libpq-devel \
    geos-devel \
    proj-devel \
    gdal-libs \
    && dnf clean all

# Application code
COPY pyproject.toml ${LAMBDA_TASK_ROOT}/
COPY packages/ ${LAMBDA_TASK_ROOT}/packages/
COPY apps/ ${LAMBDA_TASK_ROOT}/apps/
COPY scripts/ ${LAMBDA_TASK_ROOT}/scripts/
COPY alembic.ini ${LAMBDA_TASK_ROOT}/
COPY alembic/ ${LAMBDA_TASK_ROOT}/alembic/

# Python deps
RUN pip install --no-cache-dir .

# Mangum wraps FastAPI for Lambda
CMD ["apps.api.lambda_handler.handler"]
