from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "MockWithUs API"
    api_v1_prefix: str = ""
    environment: str = "development"
    debug: bool = True

    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@db:5432/mockwithus",
        alias="DATABASE_URL",
    )

    secret_key: str = Field(
        default="change-me-in-production",
        alias="SECRET_KEY",
    )
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_days: int = Field(default=7, alias="ACCESS_TOKEN_EXPIRE_DAYS")

    llm_provider: str = Field(default="groq", alias="LLM_PROVIDER")
    llm_model: str = Field(default="qwen/qwen3-32b", alias="LLM_MODEL")
    llm_fallback_provider: str | None = Field(default=None, alias="LLM_FALLBACK_PROVIDER")
    llm_fallback_model: str | None = Field(default=None, alias="LLM_FALLBACK_MODEL")
    llm_retry_jitter_seconds: float = Field(default=0.5, alias="LLM_RETRY_JITTER_SECONDS")
    llm_eval_max_concurrency: int = Field(default=2, alias="LLM_EVAL_MAX_CONCURRENCY")
    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1", alias="GROQ_BASE_URL")
    ollama_base_url: str = Field(default="http://localhost:11434/v1", alias="OLLAMA_BASE_URL")

    upload_dir: str = Field(default="/app/uploads", alias="UPLOAD_DIR")
    max_upload_size_mb: int = Field(default=5, alias="MAX_UPLOAD_SIZE_MB")
    max_answer_audio_size_mb: int = Field(default=10, alias="MAX_ANSWER_AUDIO_SIZE_MB")
    transcription_model_size: str = Field(default="base", alias="TRANSCRIPTION_MODEL_SIZE")
    transcription_device: str = Field(default="cpu", alias="TRANSCRIPTION_DEVICE")
    transcription_compute_type: str = Field(default="int8", alias="TRANSCRIPTION_COMPUTE_TYPE")
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000"], alias="CORS_ORIGINS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
