# =============================================================================
# Legal Draft AI - ML-Enabled Backend Dockerfile (Optional)
# =============================================================================
# Use this when ML/AI features (RAG, embeddings, transformers) are needed
# Build with: docker build -f Dockerfile.ml -t legal-draft-ml .
# =============================================================================

# ---- Stage 1: Builder ----
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libpq-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python build dependencies and compile wheels
COPY requirements-base.txt requirements-ml.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip wheel setuptools && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements-base.txt -r requirements-ml.txt

# ---- Stage 2: Runtime with ML ----
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime system dependencies (libpq5 not needed: psycopg2-binary bundles it)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Pre-installed venv from the builder stage (see backend/Dockerfile).
COPY --from=builder /opt/venv /opt/venv

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    VIRTUAL_ENV=/opt/venv

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy application code (alembic.ini lives here; init_db needs it)
COPY . .

# Create non-root user (and a writable model cache, see backend/Dockerfile)
RUN mkdir -p /app/.cache && \
    useradd --create-home --uid 1000 appuser && \
    chown -R appuser:appuser /app/.cache
USER appuser

EXPOSE 8000

# Liveness, not readiness (see backend/Dockerfile).
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/live')" || exit 1

CMD ["gunicorn", "main:app", "-k", "uvicorn.workers.UvicornWorker", "--workers", "1", "--bind", "0.0.0.0:8000"]
