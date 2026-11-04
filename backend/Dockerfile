# =============================================================================
# Legal Draft AI - Lightweight Backend Dockerfile (default)
# =============================================================================
# Installs ONLY requirements-base.txt (spaCy + template/cloud-LLM path).
# Torch / transformers / chromadb live in Dockerfile.ml (requirements-ml.txt).
# gunicorn is intentionally NOT in requirements.txt; the image installs it
# here because the production CMD needs it (a missing package made this image
# crash with "gunicorn: not found" on deploy).
# =============================================================================

# ---- Stage 1: Builder ----
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libpq-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python build dependencies and compile wheels (base only)
COPY requirements-base.txt ./
RUN pip install --no-cache-dir --upgrade pip wheel setuptools && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements-base.txt

# ---- Stage 2: Runtime ----
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-compiled wheels from builder
COPY --from=builder /wheels /wheels

# Install Python packages from pre-compiled wheels.
# gunicorn is installed explicitly: requirements.txt (and thus requirements-base.txt)
# does not pin it, but the production CMD below needs it. Without this line the
# container exits immediately with "executable file not found: gunicorn".
COPY requirements-base.txt ./
RUN pip install --no-cache-dir --no-index --find-links /wheels -r requirements-base.txt && \
    pip install --no-cache-dir "gunicorn>=22.0" && \
    rm -rf /wheels

# Keep memory low: disable bytecode writing for a read-only-ish runtime.
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

# Liveness, not readiness: the /health endpoint touches Postgres/Redis, so a
# database blip must never get the container killed. The readiness check is
# GET /api/v1/health (see app/api/routes/health.py).
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/live')" || exit 1

# 1 worker: background drafts are an in-process asyncio task, so a second
# worker would run its own (uncoordinated) draft queue and duplicate work.
# Scale by raising WEB_CONCURRENCY... no: scale memory-bound CPU draft workers
# explicitly (workers * NLP load). Keep 1 until drafts move to a real queue.
CMD ["gunicorn", "main:app", "-k", "uvicorn.workers.UvicornWorker", "--workers", "1", "--bind", "0.0.0.0:8000"]
