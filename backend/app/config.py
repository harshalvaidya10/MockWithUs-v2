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
    llm_model: str = Field(default="llama-3.1-70b-versatile", alias="LLM_MODEL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")

    upload_dir: str = Field(default="/app/uploads", alias="UPLOAD_DIR")
    max_upload_size_mb: int = Field(default=5, alias="MAX_UPLOAD_SIZE_MB")
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
