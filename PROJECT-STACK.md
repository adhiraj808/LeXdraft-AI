# LegalDraftAI Project Stack

Your current project is a full-stack AI-powered legal case drafting system called LegalDraftAI / LeXdraft-AI.

## 1. Overall architecture

```text
React + Vite frontend
        |
        | REST API / JSON / JWT
        v
FastAPI backend
        |
        ├── PostgreSQL — users, cases, drafts
        ├── Redis — caching and temporary case-processing data
        ├── NLP/ML pipeline
        │     ├── spaCy — preprocessing and entity extraction
        │     ├── Transformers/PyTorch — case classification
        │     ├── SentenceTransformers — embeddings
        │     ├── ChromaDB — vector search/RAG
        │     └── LLM providers/local model — draft generation
        └── ReportLab — PDF export
```

The application is containerized with Docker Compose and runs as separate frontend, backend, PostgreSQL, and Redis services.

## 2. Frontend stack

### Core technologies

- React 18
- Vite 8
- JavaScript/JSX, not TypeScript
- React Router
- Axios
- React Hot Toast
- Lucide React
- Nginx for production static serving

The frontend is located in `frontend/`.

### React structure

The main application uses:

- `BrowserRouter` for client-side routing
- React Context for authentication
- React Context for theme management
- Reusable layout and page components
- Custom hooks for API-backed state

Important frontend areas:

```text
frontend/src/
├── App.jsx
├── main.jsx
├── components/
├── hooks/
├── pages/
├── services/
└── data/
```

### Frontend pages

The application includes pages for:

- Login
- Registration
- Dashboard
- Case creation
- Chat-based case drafting
- Case list
- Case details
- Admin management

Routes are defined in `frontend/src/App.jsx`.

### API communication

`frontend/src/services/api.js` creates an Axios client with:

```text
Base URL: /api/v1
```

Depending on the environment, the API URL comes from:

```text
VITE_API_URL
```

The Axios client:

- Automatically attaches the JWT access token from `localStorage`
- Redirects users to `/login` when the API returns HTTP 401
- Exposes grouped API clients:
  - `authAPI`
  - `casesAPI`
  - `healthAPI`
  - `adminAPI`

### UI libraries

The frontend uses:

- Lucide React for icons
- React Hot Toast for notifications
- Custom CSS in `frontend/src/index.css`

Although the README describes the frontend as using TailwindCSS, the current `package.json` does not include Tailwind, PostCSS, or Autoprefixer. The current frontend appears to use custom CSS rather than Tailwind.

## 3. Backend stack

The backend is located in `backend/`.

### Web framework

- FastAPI
- Uvicorn for development/ASGI serving
- Gunicorn with Uvicorn workers for container production serving
- Pydantic v2
- Pydantic Settings

The entry point is:

```text
backend/main.py
```

FastAPI exposes automatic API documentation at:

```text
/docs
/redoc
```

### API routes

The backend currently has route groups for:

```text
/api/v1/health
/api/v1/auth
/api/v1/cases
/api/v1/rag
/api/v1/admin
```

The main functional areas are:

- User registration and login
- Google authentication
- Case submission
- Prompt-based case creation
- Case listing and retrieval
- Draft regeneration
- PDF export
- RAG-related operations
- Administrative user and case management
- Health checks for PostgreSQL and Redis

### Backend organization

```text
backend/app/
├── api/routes/
├── core/
├── db/
├── models/
├── nlp/
├── schemas/
├── services/
└── utils/
```

The project follows a layered backend design:

- `api/routes` — HTTP endpoints
- `services` — application/business logic
- `models` — SQLAlchemy database models
- `schemas` — Pydantic request/response schemas
- `core` — configuration, security, logging
- `db` — PostgreSQL and Redis setup
- `nlp` — AI processing pipeline
- `utils` — PDF generation and helpers

## 4. Database stack

### PostgreSQL

The primary database is:

- PostgreSQL 15
- PostgreSQL Docker image: `postgres:15-alpine`
- Async database access through `asyncpg`
- SQLAlchemy ORM
- Synchronous PostgreSQL support through `psycopg2-binary`
- Database migrations through Alembic

The backend uses SQLAlchemy 2.x async APIs:

```text
create_async_engine
AsyncSession
async_sessionmaker
DeclarativeBase
```

The database stores entities such as:

- Users
- Legal cases
- Generated drafts
- Extracted entities
- Draft sections
- Case metadata and status

Database migrations are located in:

```text
backend/alembic/
```

### Redis

Redis is used for:

- Case-processing cache
- Draft cache
- Temporary NLP pipeline data
- Potential session/short-lived data
- Cache invalidation after updates or deletions

The project uses:

- Redis 7
- Python `redis` package
- Async Redis client through `redis.asyncio`
- Password-protected Redis
- A default cache TTL of 24 hours

Redis is exposed only on localhost in Docker Compose:

```text
127.0.0.1:6379
```

## 5. Authentication and security

The backend authentication stack consists of:

- JWT access tokens
- `python-jose`
- Password hashing with `passlib`
- `bcrypt`
- OAuth2 bearer token handling through FastAPI
- Google Sign-In verification through:
  - `google-auth`
  - Google ID token verification

The authentication flow supports:

1. Traditional email/password registration
2. Email/password login
3. Google OAuth login
4. JWT-protected API routes
5. Role-based admin access

The frontend stores the access token in `localStorage` and sends it using:

```text
Authorization: Bearer <token>
```

The backend uses:

```text
HS256
```

for JWT signing.

## 6. AI and NLP stack

The core differentiator of the project is its NLP and legal-drafting pipeline.

The pipeline is implemented in:

```text
backend/app/nlp/pipeline.py
```

Its processing flow is:

```text
Raw case facts
    ↓
Text preprocessing
    ↓
Named entity extraction
    ↓
Case classification
    ↓
Legal precedent retrieval
    ↓
Draft generation
    ↓
Structured legal draft
```

### spaCy

Used for:

- Text processing
- Tokenization
- Named entity recognition
- Legal entity extraction
- Date, person, location, court, statute, and monetary-value detection

Configured model:

```text
en_core_web_sm
```

The Docker image downloads the spaCy model during the backend build.

There are also fallback/mock implementations for some AI libraries so that parts of the system can continue operating if a heavy model is unavailable.

### Transformers and PyTorch

The project includes:

- Hugging Face Transformers
- PyTorch
- Tokenizers
- SentencePiece
- Accelerate
- Hugging Face Hub

These support:

- Case classification
- Transformer-based model loading
- Local or hosted language model workflows
- Training utilities for classifier and NER models

The configured classifier base model is:

```text
distilbert-base-uncased
```

A locally fine-tuned classifier can be loaded from:

```text
.cache/models/classifier_model
```

The repository also contains training scripts:

```text
backend/app/nlp/training/train_classifier.py
backend/app/nlp/training/train_ner.py
```

### Sentence Transformers

The project uses:

```text
sentence-transformers
```

The RAG retriever currently references:

```text
all-MiniLM-L6-v2
```

This model converts legal text and user queries into vector embeddings.

### ChromaDB

ChromaDB provides the vector database for legal-document retrieval.

The repository contains a persistent local ChromaDB store:

```text
backend/chroma_db/
```

It is used to store and search legal documents or precedents based on semantic similarity.

The RAG flow is approximately:

```text
Case type + case facts
        ↓
SentenceTransformer embedding
        ↓
ChromaDB similarity search
        ↓
Top legal precedents
        ↓
Added to LLM generation context
```

The pipeline retrieves up to three relevant precedents before draft generation.

## 7. LLM and draft-generation stack

The project supports multiple draft-generation strategies.

### Supported providers

The backend can work with:

- Groq
- Hugging Face Inference Providers
- Generic OpenAI-compatible APIs
- OpenRouter
- Together
- vLLM
- Ollama
- llama.cpp server
- Local GGUF models
- Built-in template fallback generation

The universal LLM interface is implemented in:

```text
backend/app/nlp/llm_client.py
```

It communicates using the OpenAI-compatible endpoint:

```text
/chat/completions
```

### Provider selection

The provider is selected through:

```text
MODEL_PROVIDER
```

Supported values include:

```text
auto
hf
groq
openai
local
template
```

In `auto` mode, the application attempts to select an available provider and then falls back to local or template-based generation.

### Groq

The project supports Groq through:

```text
https://api.groq.com/openai/v1
```

The default configured model in `.env.example` is:

```text
openai/gpt-oss-20b
```

Groq is also used directly by parts of the extraction and generation code.

### Hugging Face

Hugging Face configuration supports:

- Hugging Face API token
- Hugging Face router endpoint
- Configurable model name

The configured default HF model is:

```text
zai-org/GLM-5.3
```

### Local GGUF model

The repository contains a local model file:

```text
backend/.cache/models/llama-3.2-1b-instruct.Q4_K_M.gguf
```

The configured local model path is:

```text
.cache/models/llama-3.2-1b-instruct.Q4_K_M.gguf
```

The backend also includes `llama-cpp-python` in its dependency list, although the requirements comment indicates that the local llama.cpp path is not intended to be the primary runtime route.

### Fallback generation

If cloud providers or local models are unavailable, the backend can fall back to:

- Template-based legal drafting
- Hardcoded draft section generation
- Mock NLP/model implementations in selected modules

This makes the application more resilient during development and testing.

## 8. Legal document generation

PDF generation is implemented with:

- ReportLab
- Jinja2

The PDF utility is:

```text
backend/app/utils/pdf_generator.py
```

The generated PDFs use:

- A4 page size
- Structured legal draft sections
- Paragraph formatting
- Legal document styling
- Headings and spacing
- Downloadable API responses

The frontend exposes PDF export from the case details view.

## 9. Container and deployment stack

### Docker Compose services

The project defines four main services:

```text
postgres
redis
backend
frontend
```

### Backend container

The backend uses:

```text
python:3.11-slim
```

It installs system dependencies including:

- GCC/build tools
- CMake
- PostgreSQL development libraries
- OpenMP runtime

The backend container is intended to run with:

```text
gunicorn
uvicorn.workers.UvicornWorker
```

The development Compose command instead runs:

```text
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend container

The frontend uses a two-stage build:

1. Node 20 Alpine to install dependencies and run `vite build`
2. Nginx Alpine to serve the compiled frontend

The production frontend is served by Nginx on port:

```text
5173
```

Nginx also proxies:

```text
/api/*
```

to the backend service at:

```text
http://backend:8000
```

### Persistent volumes

Docker Compose defines persistent volumes for:

- PostgreSQL data
- Redis data
- AI model cache

```text
postgres_data
redis_data
model_cache
```

## 10. Testing stack

The backend uses:

- pytest
- pytest-asyncio
- HTTPX
- aiosqlite
- Async FastAPI test clients
- Mocked Redis
- SQLAlchemy async test sessions

Test areas include:

```text
backend/tests/
├── test_api.py
├── test_nlp.py
├── test_redis_client.py
└── test_services.py
```

The test setup uses FastAPI's ASGI transport and mocks external infrastructure where appropriate.

## 11. Configuration and environment management

Configuration is handled using:

- `.env`
- `.env.example`
- `pydantic-settings`
- `python-dotenv`

Important environment variables include:

```text
SECRET_KEY
POSTGRES_*
REDIS_*
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GROQ_API_KEY
GROQ_MODEL
HUGGINGFACE_TOKEN
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
ALLOWED_ORIGINS
```

The frontend separately uses:

```text
VITE_API_URL
VITE_GOOGLE_CLIENT_ID
```

## 12. Important current-stack observations

A few details in the repository differ from the README description:

- The README lists TailwindCSS, but Tailwind is not present in `frontend/package.json`; the UI currently appears to use custom CSS.
- The backend requirements include `llama-cpp-python`, but comments in the requirements and generator indicate that local GGUF execution is optional and may not be the primary path.
- Docker's production backend command uses `gunicorn`, but `gunicorn` does not appear explicitly in the visible `requirements.txt`; this may need verification if the production container is used.
- The project is not a Next.js application; it is a Vite-powered React SPA.
- The backend is not Flask or Django; it is an async FastAPI application.
- The database layer is PostgreSQL with SQLAlchemy, not SQLite in production. SQLite/aiosqlite is mainly used for testing.
- The AI system is hybrid: it combines deterministic/template fallbacks, spaCy extraction, transformer components, vector retrieval, and optional external LLM providers.

## Final stack summary

Your project is:

```text
React 18
+ Vite
+ JavaScript/JSX
+ React Router
+ Axios
+ FastAPI
+ Python 3.11
+ Uvicorn/Gunicorn
+ PostgreSQL 15
+ SQLAlchemy 2
+ asyncpg
+ Alembic
+ Redis 7
+ JWT authentication
+ Google OAuth
+ spaCy
+ Hugging Face Transformers
+ PyTorch
+ SentenceTransformers
+ ChromaDB
+ Groq/Hugging Face/OpenAI-compatible LLM providers
+ Optional local GGUF/llama.cpp model
+ ReportLab
+ Jinja2
+ Docker Compose
+ Nginx
+ pytest
```
