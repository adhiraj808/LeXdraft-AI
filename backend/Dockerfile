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
# A venv keeps the runtime layer free of build tooling, and --mount=type=cache
# makes rebuilds after a code-only change instant instead of re-downloading
# every wheel.
FROM python:3.11-slim AS builder

WORKDIR /app

# hadolint DL3008: pin versions so builds are reproducible.
# hadolint ignore=DL3008 (build-essential/cmake/libpq-dev/libgomp1 are build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libpq-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-base.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip wheel setuptools && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements-base.txt

# ---- Stage 2: Runtime ----
FROM python:3.11-slim AS runtime

WORKDIR /app

# libpq5 is NOT needed: psycopg2-binary ships its own libpq.
# libgomp1 is needed by numpy/blis/thinc (spaCy).
# hadolint ignore=DL3008 (libgomp1 version is tied to the Debian release)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# The venv (with every wheel already installed) replaces the old
# "COPY /wheels; pip install; rm -rf /wheels" dance, which kept the wheels in
# the image twice because deleting them in a later layer does not shrink it.
COPY --from=builder /opt/venv /opt/venv

# Keep memory low: disable bytecode writing for a read-only-ish runtime.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    VIRTUAL_ENV=/opt/venv

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy application code (alembic.ini lives here; init_db needs it)
COPY . .

# Create non-root user. /app/.cache must exist and be owned by appuser BEFORE
# the model_cache volume is mounted, otherwise Docker creates it as root and
# the app cannot write model downloads to it.
RUN mkdir -p /app/.cache && \
    useradd --create-home --uid 1000 appuser && \
    chown -R appuser:appuser /app/.cache
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
