"""Application configuration using Pydantic Settings.

Values are resolved in this order (highest priority first):

1. real environment variables (Docker, ECS, Kubernetes, CI ...),
2. ``backend/.env``  - local development (run from ``backend/``),
3. ``<repo root>/.env`` - shared with docker-compose,
4. the defaults declared below.

The env files are located relative to this file (not the current working
directory), so the app, Alembic, the seed script and the tests all see the same
configuration no matter where they are started from.
"""

import json
import ssl
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional
from urllib.parse import quote

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import URL

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent

# SECRET_KEY values that must never be used outside DEBUG mode.
INSECURE_SECRET_KEYS = {
    "",
    "dev-secret-key-change-in-production",
    "change-me",
    "changeme",
    "secret",
}

POSTGRES_SSL_MODES = {
    "",
    "disable",
    "allow",
    "prefer",
    "require",
    "verify-ca",
    "verify-full",
}


def _split_list(value: Any) -> Any:
    """Accept JSON (``["a","b"]``) or comma separated (``a,b``) list values."""
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            return json.loads(text)
        return [item.strip() for item in text.split(",") if item.strip()]
    return value


def build_asyncpg_ssl(mode: str, root_cert: str = "") -> Any:
    """Translate a libpq style ``sslmode`` into the ``ssl`` argument of asyncpg.

    Returns ``None`` when no mode is configured so the driver default applies.
    """
    mode = (mode or "").strip().lower()
    if not mode:
        return None
    if mode == "disable":
        return False
    if mode in ("allow", "prefer"):
        return mode

    context = ssl.create_default_context(cafile=root_cert or None)
    if mode == "require":  # encrypted, certificate not verified (same as libpq)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    elif mode == "verify-ca":  # certificate chain verified, hostname not
        context.check_hostname = False
    # "verify-full": the default context verifies chain + hostname
    return context


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # unrelated keys in .env (VITE_*, COMPOSE_*, ...) must not crash the app
    )

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "LegalDraftAI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    # Serve /docs and /redoc. Set to false in production if you do not want the
    # API surface browsable.
    DOCS_ENABLED: bool = True
    # Hard cap for request bodies (bytes). Checked on Content-Length *and* while streaming.
    MAX_REQUEST_BYTES: int = 1_048_576

    # ── Security ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Google Sign-In: the OAuth Client ID from Google Cloud Console. The backend
    # verifies the credential's `aud` claim against it. Empty = Google login disabled.
    GOOGLE_CLIENT_ID: str = ""

    # Browser origins allowed by CORS and Host header values accepted by the API.
    # Both accept JSON (["a","b"]) or comma separated (a,b) values.
    ALLOWED_ORIGINS: Annotated[List[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]
    # Add your domain here when deploying (e.g. api.example.com or *.example.com).
    # "backend" is the docker-compose service name used by the nginx proxy.
    ALLOWED_HOSTS: Annotated[List[str], NoDecode] = [
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "backend",
    ]

    # ── Rate limiting (slowapi / `limits` syntax, e.g. "10/minute") ───────────
    RATE_LIMIT_DEFAULT: str = "300/minute"  # every endpoint without its own limit
    RATE_LIMIT_AUTH: str = "10/minute"  # login / register / google (brute-force guard)
    RATE_LIMIT_DRAFTS: str = (
        "25/15minutes"  # endpoints that call the LLM to draft a case
    )
    RATE_LIMIT_QA: str = "30/minute"  # authenticated legal Q&A
    RATE_LIMIT_PUBLIC_QA: str = "5/minute"  # anonymous legal Q&A (only if enabled)
    # "memory://" is per-process. Use your Redis URL (redis://...) when running
    # more than one container/worker so the limits are shared.
    RATE_LIMIT_STORAGE_URI: str = "memory://"
    # Anonymous Q&A spends LLM credits for anyone on the internet - opt in explicitly.
    PUBLIC_QA_ENABLED: bool = False

    # ── LLM providers ────────────────────────────────────────────────────────
    # Groq online LLM (optional). NEVER commit this key.
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-20b"

    # Hugging Face Inference API (optional). Both token names are accepted.
    HF_API_TOKEN: str = ""
    HUGGINGFACE_TOKEN: str = ""
    HF_MODEL: str = "zai-org/GLM-5.3"
    HF_BASE_URL: str = "https://router.huggingface.co/v1"

    # Universal OpenAI-compatible endpoint (Groq, HF, OpenRouter, Together,
    # vLLM, Ollama, llama.cpp server ...).
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""

    # auto | hf | groq | openai | local | template
    MODEL_PROVIDER: str = "auto"
    LLM_TIMEOUT_SECONDS: float = 60.0
    # Reasoning models spend part of this budget on hidden "thinking" tokens.
    LLM_MAX_TOKENS: int = 2048
    # Pause between sections so free-tier per-minute limits are not hit.
    LLM_SECTION_DELAY_SECONDS: float = 4.0
    # After a provider call fails, skip that provider for this long (seconds).
    LLM_FAILURE_COOLDOWN_SECONDS: float = 60.0

    # ── PostgreSQL ───────────────────────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "legal_draft_db"
    POSTGRES_USER: str = "legaluser"
    POSTGRES_PASSWORD: str = "legalpass"
    # libpq-style TLS mode: disable | allow | prefer | require | verify-ca | verify-full.
    # Empty keeps the driver default. Use "require" (or verify-full) for AWS RDS.
    POSTGRES_SSLMODE: str = ""
    # CA bundle for verify-ca / verify-full (e.g. the AWS RDS global-bundle.pem).
    POSTGRES_SSLROOTCERT: str = ""
    POSTGRES_CONNECT_TIMEOUT: float = 10.0
    # Small pool on purpose: every Postgres connection costs ~10 MB on the server.
    POSTGRES_POOL_SIZE: int = 3
    POSTGRES_MAX_OVERFLOW: int = 2
    POSTGRES_POOL_RECYCLE_SECONDS: int = 1800
    SQL_ECHO: bool = (
        False  # log every SQL statement (very chatty, leaks data into logs)
    )

    # ── Redis (cache + progress pub/sub) ─────────────────────────────────────
    # Redis only caches data that also lives in PostgreSQL, so by default the app
    # falls back to a small in-process store when Redis is unreachable.
    REDIS_ENABLED: bool = True  # false = never connect, always use the in-process store
    REDIS_REQUIRED: bool = False  # true = refuse to start when Redis is unreachable
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_USERNAME: str = ""
    REDIS_PASSWORD: str = ""
    REDIS_SSL: bool = False  # true = rediss:// (AWS ElastiCache in-transit encryption)
    REDIS_DB: int = 0
    REDIS_TTL_SECONDS: int = 86400  # 24 hours
    REDIS_MAX_CONNECTIONS: int = 5
    REDIS_CONNECT_TIMEOUT: float = 3.0
    REDIS_FALLBACK_MAX_KEYS: int = 500

    # ── NLP / ML ─────────────────────────────────────────────────────────────
    SPACY_MODEL: str = "en_core_web_sm"
    HF_MODEL_CLASSIFIER: str = (
        "distilbert-base-uncased"  # base model used by the training script
    )
    # Locally fine-tuned classifier (output of app/nlp/training/train_classifier.py).
    # Only used if it exists; torch/transformers are imported lazily for it.
    CLASSIFIER_MODEL_PATH: str = ".cache/models/classifier_model"
    USE_GPU: bool = False
    MODEL_CACHE_DIR: str = ".cache/models"

    # RAG (ChromaDB + embeddings). Heavy, so it is loaded on first use unless
    # RAG_EAGER_LOAD=true. ENABLE_RAG=false skips it completely.
    ENABLE_RAG: bool = True
    RAG_EAGER_LOAD: bool = False
    # auto | onnx | sentence-transformers. "auto" prefers ChromaDB's bundled ONNX
    # all-MiniLM-L6-v2 (no PyTorch needed) and falls back to sentence-transformers.
    RAG_EMBEDDING_BACKEND: str = "auto"

    # Local GGUF model through llama-cpp-python. Off by default: it needs an extra
    # package and ~1 GB of RAM once loaded (it is loaded lazily, only if enabled
    # and no cloud provider produced the text).
    ENABLE_LOCAL_LLM: bool = False
    GGUF_MODEL_PATH: str = ".cache/models/llama-3.2-1b-instruct.Q4_K_M.gguf"
    GGUF_QUANTIZATION: str = "Q4_K_M"
    GGUF_CONTEXT_WINDOW: int = 2048
    GGUF_GPU_LAYERS: int = 0  # 0 = CPU only

    # How many drafts may run the NLP pipeline at the same time.
    MAX_CONCURRENT_DRAFTS: int = 2
    # Cases stuck in pending/processing longer than this are marked failed at startup
    # (their in-process background task died with the previous server process).
    STALE_CASE_MINUTES: int = 15

    # ── Validators ───────────────────────────────────────────────────────────
    @field_validator("ALLOWED_ORIGINS", "ALLOWED_HOSTS", mode="before")
    @classmethod
    def _parse_list(cls, value: Any) -> Any:
        return _split_list(value)

    @field_validator("POSTGRES_SSLMODE")
    @classmethod
    def _check_sslmode(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in POSTGRES_SSL_MODES:
            raise ValueError(
                f"POSTGRES_SSLMODE must be one of {sorted(POSTGRES_SSL_MODES - {''})}"
            )
        return value

    @field_validator("RAG_EMBEDDING_BACKEND")
    @classmethod
    def _check_rag_backend(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in ("auto", "onnx", "sentence-transformers"):
            raise ValueError(
                "RAG_EMBEDDING_BACKEND must be auto, onnx or sentence-transformers"
            )
        return value

    # ── Derived values ───────────────────────────────────────────────────────
    def _postgres_url(self, driver: str, query: Optional[Dict[str, str]] = None) -> URL:
        # URL.create() percent-encodes the password, so "p@ss/word:1#" just works.
        return URL.create(
            drivername=driver,
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
            query=query or {},
        )

    @property
    def database_url(self) -> URL:
        """SQLAlchemy URL for the async engine (asyncpg)."""
        return self._postgres_url("postgresql+asyncpg")

    @property
    def database_url_sync(self) -> URL:
        """SQLAlchemy URL for Alembic (psycopg2)."""
        # connect_timeout keeps `alembic upgrade` from hanging when the DB is down.
        query: Dict[str, str] = {
            "connect_timeout": str(max(1, int(self.POSTGRES_CONNECT_TIMEOUT)))
        }
        if self.POSTGRES_SSLMODE:
            query["sslmode"] = self.POSTGRES_SSLMODE
        if self.POSTGRES_SSLROOTCERT:
            query["sslrootcert"] = self.POSTGRES_SSLROOTCERT
        return self._postgres_url("postgresql+psycopg2", query)

    @property
    def DATABASE_URL(self) -> str:
        return self.database_url.render_as_string(hide_password=False)

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return self.database_url_sync.render_as_string(hide_password=False)

    @property
    def DATABASE_URL_SAFE(self) -> str:
        """Same as DATABASE_URL but with the password masked - safe to log."""
        return self.database_url.render_as_string(hide_password=True)

    def asyncpg_connect_args(self) -> Dict[str, Any]:
        args: Dict[str, Any] = {
            "timeout": self.POSTGRES_CONNECT_TIMEOUT,
            "server_settings": {"application_name": self.APP_NAME},
        }
        ssl_arg = build_asyncpg_ssl(self.POSTGRES_SSLMODE, self.POSTGRES_SSLROOTCERT)
        if ssl_arg is not None:
            args["ssl"] = ssl_arg
        return args

    @property
    def REDIS_URL(self) -> str:
        scheme = "rediss" if self.REDIS_SSL else "redis"
        credentials = ""
        if self.REDIS_PASSWORD or self.REDIS_USERNAME:
            credentials = f"{quote(self.REDIS_USERNAME, safe='')}:{quote(self.REDIS_PASSWORD, safe='')}@"
        return f"{scheme}://{credentials}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    def resolve_backend_path(self, path: str) -> str:
        """Resolve a relative path (e.g. ``.cache/models/x.gguf``) against ``backend/``."""
        candidate = Path(path)
        return str(candidate if candidate.is_absolute() else BACKEND_DIR / candidate)

    def assert_secure_for_runtime(self) -> None:
        """Refuse to run a non-debug server with a guessable JWT signing key."""
        if self.DEBUG:
            return
        if self.SECRET_KEY in INSECURE_SECRET_KEYS or len(self.SECRET_KEY) < 32:
            raise RuntimeError(
                "SECRET_KEY is missing, a known default, or shorter than 32 characters. "
                'Generate one with:  python -c "import secrets; print(secrets.token_urlsafe(48))"  '
                "and set it in .env (or DEBUG=true for local development only)."
            )


settings = Settings()
