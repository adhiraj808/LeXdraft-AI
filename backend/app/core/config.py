"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "LegalDraftAI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Google Sign-In — the OAuth Client ID created in Google Cloud Console.
    # The backend verifies incoming credentials' `aud` claim against this value.
    GOOGLE_CLIENT_ID: str = ""

    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "legal_draft_db"
    POSTGRES_USER: str = "legaluser"
    POSTGRES_PASSWORD: str = "legalpass"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_TTL_SECONDS: int = 86400  # 24 hours

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # NLP / ML Models
    HF_MODEL_CLASSIFIER: str = "distilbert-base-uncased"
    # Path to a locally fine-tuned classifier checkpoint (output of
    # app/nlp/training/train_classifier.py). Only used if it actually exists —
    # the base HF_MODEL_CLASSIFIER has no trained classification head and must
    # never be used directly for predictions (see CaseClassifier.load()).
    CLASSIFIER_MODEL_PATH: str = ".cache/models/classifier_model"
    HF_MODEL_GENERATOR: str = "google/flan-t5-base"
    GGUF_MODEL_PATH: str = ".cache/models/llama-3.2-1b-instruct.Q4_K_M.gguf"
    SPACY_MODEL: str = "en_core_web_sm"
    USE_GPU: bool = False
    MODEL_CACHE_DIR: str = ".cache/models"

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
