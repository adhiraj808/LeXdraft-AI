# Local PostgreSQL + pgAdmin 4 — connect the app to a local database

This is for running the backend **without Docker** (Docker already starts its own
Postgres, and pgAdmin can point at that one instead — see Step 7).

> **pgAdmin is not a database.** It is only a GUI. You also need a PostgreSQL
> server. The EDB installer below gives you both.

---

## 1. What to download, and from where

| Tool | Where | Notes |
|---|---|---|
| **PostgreSQL 15+ + pgAdmin 4 (one file)** | https://www.postgresql.org/download/windows/ → "Download the installer" (EDB) | The big installer contains both the server and pgAdmin. **This is the one you want.** |
| pgAdmin 4 (standalone, only if the server already runs) | https://www.pgadmin.org/download/ | One file per update; no server included. |
| Python 3.11+ | https://www.python.org/downloads/ | Tick **"Add python.exe to PATH"** during install. |
| Node.js 20+ | https://nodejs.org/ | Only needed for the frontend. |
| Docker Desktop (optional) | https://www.docker.com/products/docker-desktop/ | Only for the Docker route. |
| Redis — **optional** | https://memurai.com (Windows) or run Redis in Docker | The app works without Redis (in-process cache). See `REDIS_ENABLED` in `../.env.example`. |

**Version note:** the Docker image uses `postgres:15-alpine`, and the local
defaults in `backend/app/core/config.py` assume PostgreSQL 15+. Install 15 or
newer (16/17 are fine).

**Port conflict warning:** the EDB installer creates a Windows service
`postgresql-x64-15` listening on **5432**, and the Docker Postgres also binds
5432 (on `127.0.0.1` only, from `docker-compose.yml`). **Run one or the other.**
If you use Docker, leave the service stopped (`services.msc` → stop it, or
`Set-Service postgresql-x64-15 -Status Stopped` in an admin PowerShell).

---

## 2. Install PostgreSQL + pgAdmin

1. Run the EDB installer.
2. **Service account:** `Network Service` (the default) is fine.
3. **Port:** `5432` (default).
4. **Locale:** leave the default.
5. **Data directory:** leave the default (`C:\Program Files\PostgreSQL\15\data`).
6. Remember the **superuser password** (`postgres`) you set — you need it once,
   in Step 3.
7. Tick **"Launch pgAdmin 4"** at the end, or open it later from the Start menu.

Verify the service is running: `services.msc` → `postgresql-x64-15` → *Running*.

---

## 3. Create the login role and database the app expects

The app's defaults (`backend/app/core/config.py`) are:

| Setting | Default |
|---|---|
| Host | `localhost` |
| Port | `5432` |
| Database | `legal_draft_db` |
| User | `legaluser` |
| Password | `legalpass` |

**Option A — the defaults (fastest):** change only the password, then create
the role and database in pgAdmin:

1. Open **pgAdmin 4** → *Servers* → enter the `postgres` password when asked.
2. Right-click the server → **Query Tool**, and run:

```sql
ALTER USER postgres WITH PASSWORD 'pick-a-strong-one';

CREATE ROLE legaluser WITH LOGIN PASSWORD 'legalpass';
CREATE DATABASE legal_draft_db OWNER legaluser;
```

3. In the **Query Tool** pane, also run the project's extension script:
   open `scripts/init_db.sql` and execute it (or skip it — the app creates
   UUIDs in Python, so `pgcrypto` is not required).

**Option B — your own names/password:** create them as above with your chosen
values, then write those exact values into your `.env` (Step 5). The app reads
`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`.

> Passwords with special characters (`@`, `/`, `:`, `%`) work. The URL is built
> with `URL.create()`, which percent-encodes the password, and Alembic gets the URL
> object directly — no more `configparser` interpolation breakage.

---

## 4. Check the server is reachable

```powershell
psql -h localhost -U legaluser -d legal_draft_db
```

(or use a pgAdmin **Query Tool** on the new database). If it asks for a password,
enter the one from Step 3.

If `psql` is not on your `PATH`, use the *PostgreSQL Shell* shortcut from the
Start menu, or run
`& "C:\Program Files\PostgreSQL\15\bin\psql.exe" -h localhost -U legaluser -d legal_draft_db`.

---

## 5. Configure the app (`.env`)

The settings loader
(`backend/app/core/config.py`) reads, in order:

1. **Real environment variables** (Docker, ECS, Kubernetes, CI…) ← highest
2. `<repo root>/.env` ← **the one you edit for a normal local run**
3. `backend/.env` ← optional, overrides the root file
4. Built-in defaults

The files are found **relative to the code**, not relative to the directory you
start the server from, so `alembic`, the seed script and the tests all see the
same configuration.

```powershell
cd C:\Users\<you>\Desktop\Legal-Draft-System
copy .env.example .env
```

Then edit `.env`:

```ini
# For a local (non-Docker) PostgreSQL: these are the defaults, so normally
# nothing to change. Only change POSTGRES_PASSWORD if you used a different one.
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=legal_draft_db
POSTGRES_USER=legaluser
POSTGRES_PASSWORD=legalpass

# Local dev only. DEBUG=true also turns SQL statement logging OFF (SQL_ECHO is
# separate and defaults to false), and skips the JWT secret check below.
DEBUG=true

# Required when DEBUG=false: must be at least 32 characters.
SECRET_KEY=<generate one - see below>
```

Generate a secret key:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Without a `SECRET_KEY` of ≥ 32 characters the app **refuses to start** with
`DEBUG=false`. That is intentional — a guessable JWT signing key lets anyone
forge admin tokens.

---

## 6. Install dependencies and start the backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

`requirements.txt` is the **lightweight** set (spaCy + template/cloud-LLM
drafting). For semantic precedent retrieval (ChromaDB) add
`requirements-ml.txt`; for the local GGUF model add
`requirements-local-llm.txt`; for training add `requirements-training.txt`.

Start it:

```powershell
python -c "import uvicorn; uvicorn.run('main:app', host='0.0.0.0', port=8000, reload=True)"
# or:
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**What happens on startup** (`backend/main.py` lifespan):

1. `init_db()` checks the connection, then runs **all Alembic migrations**
   inside a PostgreSQL advisory lock, so several workers cannot race each other.
   `CREATE EXTENSION pgcrypto` is not needed.
2. Redis is initialised — if it is unreachable the app **falls back to a small
   in-process cache** and logs a warning (set `REDIS_REQUIRED=true` to make it
   fatal instead, or `REDIS_ENABLED=false` to never connect).
3. The NLP pipeline (spaCy) loads in a background task; the API answers
   `GET /api/v1/health` immediately and the pipeline finishes in the background.
4. Any case left in `pending`/`processing` by a previous process is marked
   `failed` (it was orphaned by the restart).

Then open **http://localhost:8000/docs** and **http://localhost:8000/api/v1/health**.

To seed a demo user and three sample cases:

```powershell
cd backend
python ..\scripts\seed_data.py
# -> demo_advocate / Demo@1234
```

---

## 7. See the data in pgAdmin

pgAdmin → *Servers* → expand `legal_draft_db` → *Schemas → public → Tables* →
`users`, `cases`, `drafts`. Right-click a table → **View/Insert Data** → **Sort/Filter**
(or the Query Tool).

### Docker Postgres instead?

If you run `docker compose up`, Postgres is already on `127.0.0.1:5432` with the
values from your `.env`. In pgAdmin: *Add Server* → **General** tab:

| Field | Value |
|---|---|
| Name | `LegalDraft (docker)` |
| Host name / address | `localhost` |
| Port | `5432` |
| Maintenance database | `legal_draft_db` |
| Username | `legaluser` |
| Password | the `POSTGRES_PASSWORD` from `.env` |

and tick **Save password**. The app gets `POSTGRES_HOST=postgres` injected by
Compose, so the backend `.env` values do not need to change.

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `Cannot connect to PostgreSQL ...` | Service stopped? Check `services.msc`. Wrong password? Re-run Step 3's `ALTER USER`. `localhost` resolving to IPv6 first? Use `127.0.0.1` for `POSTGRES_HOST`. |
| `address already in use` on 5432 | Docker Postgres and the Windows service are both running. Stop one (see the warning in §1). |
| `password authentication failed` | The role created in pgAdmin differs from `.env`. The app reads the **repo-root** `.env` first when run from outside `backend/`. |
| `SECRET_KEY ... shorter than 32 characters` | Generate one (Step 5) or set `DEBUG=true` for local development only. |
| `Redis unreachable ... Continuing with an in-process cache` | **Not an error.** It is the intended fallback; set `REDIS_ENABLED=false` to silence it, or start Redis / run `docker compose up redis`. |
| Alembic complains about `sqlalchemy.url` | It is empty on purpose now — the URL is built from the `POSTGRES_*` settings in `alembic/env.py`. Never put credentials in `alembic.ini`. |
| Backend runs but drafts say "AI service not ready" | Give the NLP pipeline ~30–60 s to finish loading; check `/api/v1/health` → `nlp_pipeline`. |
| `gunicorn: not found` | Use the Docker image (it installs gunicorn) or run `uvicorn` directly. `gunicorn` is in `requirements-base.txt`. |

---

## 9. Memory tips for a local run

- `requirements.txt` no longer pulls `torch` / `transformers` / `chromadb` /
  `llama-cpp-python`. Those live in `requirements-ml.txt` (ChromaDB),
  `requirements-local-llm.txt` (GGUF) and `requirements-training.txt` (torch).
  Importing torch alone costs ~0.3–0.5 GB of RAM and a lot of Windows commit
  charge, which is what makes the page file balloon.
- The classifier and the RAG retriever import torch / ChromaDB / sentence-
  transformers **lazily, only when they are actually used**
  (`ENABLE_RAG=false` skips RAG entirely; `RAG_EAGER_LOAD` controls whether it
  loads at startup).
- The Postgres pool defaults to **3 + 2 overflow** — each connection costs
  ~10 MB on the server. Raise `POSTGRES_POOL_SIZE` / `POSTGRES_MAX_OVERFLOW`
  only if you need more concurrency.
- `MAX_CONCURRENT_DRAFTS=2` (default) limits how many drafts run at once.
- In Docker, `docker-compose.yml` caps memory (`backend: 1g`, `postgres: 512m`,
  `redis: 128m`) and runs Postgres with small `shared_buffers` / `work_mem`.
- `PYTHONDONTWRITEBYTECODE=1` is set in the Docker images.

See also [`AWS-DEPLOY.md`](./AWS-DEPLOY.md) for moving this to AWS (RDS, ElastiCache,
ECS Fargate, ALB, S3/CloudFront).
