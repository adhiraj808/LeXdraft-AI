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
RUN pip install --no-cache-dir --upgrade pip wheel setuptools && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements-base.txt -r requirements-ml.txt

# ---- Stage 2: Runtime with ML ----
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-compiled wheels from builder
COPY --from=builder /wheels /wheels

# Install Python packages from pre-compiled wheels.
# gunicorn is installed explicitly (see backend/Dockerfile): the production CMD
# needs it, but requirements.txt does not pin it.
COPY requirements-base.txt requirements-ml.txt ./
RUN pip install --no-cache-dir --no-index --find-links /wheels -r requirements-base.txt -r requirements-ml.txt && \
    pip install --no-cache-dir "gunicorn>=22.0" && \
    rm -rf /wheels

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy application code (alembic.ini lives here; init_db needs it)
COPY . .

# Create non-root user
RUN useradd --create-home --uid 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Liveness, not readiness (see backend/Dockerfile).
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/live')" || exit 1

CMD ["gunicorn", "main:app", "-k", "uvicorn.workers.UvicornWorker", "--workers", "1", "--bind", "0.0.0.0:8000"]
