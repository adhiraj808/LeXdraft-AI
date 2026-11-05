# AI-Powered Legal Case Drafting System

An intelligent full-stack platform that accepts unstructured case facts, classifies the case type, extracts legal entities via NER, and generates professionally formatted legal drafts using spaCy + cloud LLMs (or hardcoded templates when no model is configured).

## Features

- **Automated Case Classification**: Keyword classifier (with optional transformer fallback) identifies the case type (Criminal, Civil, Family Law, Labour, Constitutional, Property Dispute) from raw facts.
- **Named Entity Recognition (NER)**: spaCy extracts persons, organisations, dates, statutes, courts and money amounts.
- **Dynamic Draft Generation**: OpenAI-compatible LLM providers (Groq, Hugging Face, any `/chat/completions` endpoint) or hardcoded case-type-aware templates. No LLM key = templates, no failure.
- **RAG precedent retrieval** (optional): ChromaDB + all-MiniLM-L6-v2 embeddings, loaded lazily on first use.
- **Legal Q&A (Legal Assistant)**: plain-language answers in English/Hindi with template fallbacks.
- **PDF Export**: ReportLab generates professional PDFs.
- **Modern Dashboard & AI Chat**: React app with chat-based drafting, case list/detail, admin panel.

## Tech Stack

- **Backend**: FastAPI (Python 3.11/3.12), SQLAlchemy 2 async + asyncpg, Alembic, Pydantic Settings, JWT (python-jose + bcrypt), slowapi, ReportLab.
- **Frontend**: React 18, Vite 8, React Router, Axios, Lucide React, custom CSS (no Tailwind), nginx (production).
- **NLP / RAG**: spaCy (NER), transformers (optional, fine-tuned classifier), ChromaDB + sentence-transformers/ONNX (optional, RAG), llama-cpp-python (optional, local GGUF).
- **Infra**: Docker + Docker Compose, PostgreSQL 15, Redis 7 (optional — in-process cache fallback).
- **CI/CD**: GitHub Actions (tests/lint/build), GHCR on `main`.

> **Memory note:** the default backend image installs only `requirements-base.txt`
> (spaCy + template/cloud-LLM path, ~300–400 MB). Torch / transformers / ChromaDB
> are **not** in that image — they live in `requirements-ml.txt` / `Dockerfile.ml`.
> Importing torch alone costs ~0.3–0.5 GB RAM, so the split is what keeps the app lean.

## Project Structure

```
legal_draft_system/
├── backend/                  # FastAPI backend + ML/NLP
│   ├── app/
│   │   ├── api/routes/       # health, auth, cases, rag, admin, fir_analysis (Q&A)
│   │   ├── core/             # config, security, middleware, rate_limit, logging
│   │   ├── db/               # postgres (SQLAlchemy) + redis_client
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # auth_service, case_service
│   │   ├── nlp/              # pipeline, classifier, generator, llm_client, retriever
│   │   └── utils/            # pdf_generator
│   ├── alembic/              # migrations
│   ├── tests/                # pytest (aiosqlite, mocked Redis/NLP)
│   ├── main.py
│   ├── requirements.txt                  # lightweight runtime (= requirements-base.txt)
│   ├── requirements-base.txt             # runtime without ML
│   ├── requirements-ml.txt               # ChromaDB only (RAG)
│   ├── requirements-local-llm.txt        # llama-cpp-python (GGUF)
│   ├── requirements-training.txt         # torch / transformers (training only)
│   ├── requirements-dev.txt              # pytest, ruff, mypy
│   ├── Dockerfile                        # lightweight backend (default)
│   ├── Dockerfile.ml                     # ML-enabled backend (RAG/embeddings)
│   └── .ruff.toml / .mypy.ini
├── frontend/                 # React + Vite + nginx
│   ├── src/                  # pages, components, hooks, services/api.js
│   ├── nginx.conf            # prod proxy (/api/ → backend) + SPA fallback
│   ├── vite.config.js
│   └── Dockerfile
├── docs/
│   ├── LOCAL-POSTGRES-PGADMIN.md   # local PostgreSQL + pgAdmin 4 setup
│   └── AWS-DEPLOY.md               # RDS / ElastiCache / ECS Fargate / ALB
├── scripts/                  # init_db.sql, seed_data.py, download_models.py
├── docker-compose.yml
├── run-it.md                 # personal scratch notes (git-ignored, never commit)
├── .env.example
└── Makefile
```

## Setup & Installation

### Prerequisites

- Docker + Docker Compose **(recommended)**, or
- Python 3.11+ and Node.js 20+ for a native run
- PostgreSQL 15+ if you run the backend natively — see `docs/LOCAL-POSTGRES-PGADMIN.md`

### Quick Start with Docker

```bash
git clone https://github.com/adhiraj808/LeXdraft-AI.git
cd Legal-Draft-System

# 1) create .env from the example and fill in real values (never commit .env)
cp .env.example .env
#    edit .env: SECRET_KEY (≥32 chars), POSTGRES_PASSWORD, REDIS_PASSWORD, GROQ_API_KEY (optional)

# 2) build + run (Postgres + Redis + backend + frontend)
docker compose up --build -d

# 3) verify
curl http://localhost:8000/api/v1/health
```

- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs (disabled when `DOCS_ENABLED=false`)
- Health: http://localhost:8000/api/v1/health (readiness) · `/health/live` (liveness)

`docker-compose.yml` publishes Postgres on `127.0.0.1:5432` only (local pgAdmin access),
Redis on `127.0.0.1:6379`, backend on `8000`, frontend on `5173`. Memory caps:
backend `1g`, postgres `512m`, redis `128m`, frontend `64m`.

For the ML/RAG image use `Dockerfile.ml` (uncomment the `backend-ml` service in `docker-compose.yml`).

### Local Development (no Docker)

You need a local PostgreSQL — see `docs/LOCAL-POSTGRES-PGADMIN.md` for the full
step-by-step (create `legal_draft_db` + `legaluser` in pgAdmin, edit `.env`, start the stack).

#### Backend

```powershell
# Windows PowerShell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# run (hot reload)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# production style (1 worker - background drafts are in-process tasks)
gunicorn main:app -k uvicorn.workers.UvicornWorker --workers 1 --bind 0.0.0.0:8000
```

On startup the app runs Alembic migrations (advisory-locked), connects to
PostgreSQL, and loads spaCy in the background. Redis is optional: if unreachable,
the app falls back to a small in-process cache and logs a warning.

> `requirements.txt` is the lightweight set. For semantic retrieval (ChromaDB):
> `pip install -r requirements.txt -r requirements-ml.txt`. For local GGUF:
> `pip install -r requirements.txt -r requirements-local-llm.txt` and set
> `ENABLE_LOCAL_LLM=true`.

#### Frontend

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173, proxies /api → localhost:8000
```

#### Tests

```powershell
cd backend
pip install -r requirements.txt -r requirements-dev.txt
pytest -q      # 18 tests, aiosqlite (no real Postgres/Redis needed)
ruff check .   # see backend/.ruff.toml
mypy --ignore-missing-imports .   # see backend/.mypy.ini
```

### Environment

Config is Pydantic Settings (`backend/app/core/config.py`). Precedence:

1. Real environment variables (Docker, ECS, Kubernetes, CI…) ← highest
2. `<repo root>/.env` ← **edit this for a normal local run**
3. `backend/.env` ← optional override
4. Built-in defaults

Key variables (full list in `.env.example`):

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | JWT signing key (≥32 chars when `DEBUG=false`) |
| `DEBUG` | `true` for local dev only |
| `POSTGRES_*` | host/port/db/user/password + `POSTGRES_SSLMODE` (use `require` for AWS RDS) |
| `REDIS_*` | host/port/password + `REDIS_ENABLED` / `REDIS_SSL` / `REDIS_REQUIRED` |
| `ALLOWED_ORIGINS` / `ALLOWED_HOSTS` | CORS + Host-header whitelist (JSON array or comma-separated) |
| `GROQ_API_KEY` / `GROQ_MODEL` | cloud LLM provider |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | any OpenAI-compatible endpoint |
| `MODEL_PROVIDER` | `auto` · `hf` · `groq` · `openai` · `local` · `template` |
| `ENABLE_RAG` / `RAG_EAGER_LOAD` / `RAG_EMBEDDING_BACKEND` | RAG controls (lazy by default) |
| `ENABLE_LOCAL_LLM` | local GGUF fallback (off by default) |
| `PUBLIC_QA_ENABLED` | anonymous Q&A (off by default — it spends LLM credits) |

## Documentation

- **[Local PostgreSQL + pgAdmin 4](docs/LOCAL-POSTGRES-PGADMIN.md)** — downloads, creating `legal_draft_db`/`legaluser`, `.env` mapping, troubleshooting, memory tips.
- **[AWS deploy guide](docs/AWS-DEPLOY.md)** — RDS Postgres (TLS), ElastiCache Redis, ECS Fargate + ALB, S3/CloudFront, Secrets Manager, data migration, cost estimates.

## License

MIT License — see [LICENSE.md](./LICENSE.md).
Source: [adhiraj808/LeXdraft-AI](https://github.com/adhiraj808/LeXdraft-AI)
