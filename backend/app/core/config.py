"""Application settings, loaded from environment variables (and an optional .env file)."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
# Serverless hosts (Vercel) only allow writes under /tmp, which is per-instance and ephemeral.
DATA_DIR = Path(os.environ.get("DATA_DIR") or ("/tmp/datapilot" if os.environ.get("VERCEL") else BACKEND_DIR / "data"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Metadata store: conversations, messages, query runs, registered data sources.
    database_url: str = f"sqlite:///{(DATA_DIR / 'datapilot.db').as_posix()}"
    run_migrations_on_startup: bool = True

    # Demo analytics database, registered automatically as a data source on startup.
    demo_database_url: str | None = f"sqlite:///{(DATA_DIR / 'demo_sales.db').as_posix()}"
    demo_database_name: str = "Sales Demo"
    # Optional separate URL with write access, used only to seed the demo database.
    demo_seed_database_url: str | None = None

    # Used to encrypt stored data-source credentials. Must be set in production.
    secret_key: SecretStr = SecretStr("dev-only-insecure-secret-change-me")

    # LLM
    # anthropic / openai need a paid key; gemini has a free tier; ollama runs locally for free.
    llm_provider: Literal["anthropic", "openai", "gemini", "ollama", "none"] = "anthropic"
    llm_model: str | None = None
    # Override the API base URL (e.g. a remote Ollama server or another OpenAI-compatible API).
    llm_base_url: str | None = None
    llm_timeout_seconds: float = 90.0
    # Models to try, in order, when the main one is overloaded or rate limited (OpenAI-compatible
    # providers). Unset uses the provider's defaults (Gemini has some); '[]' turns fallbacks off.
    llm_fallback_models: list[str] | None = None
    anthropic_api_key: SecretStr | None = None
    anthropic_fallbacks: bool = True
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None

    # Query execution guard rails
    query_timeout_seconds: float = 15.0
    max_result_rows: int = Field(default=1000, ge=1, le=10_000)
    default_row_limit: int = Field(default=200, ge=1, le=10_000)
    max_sql_repair_attempts: int = Field(default=2, ge=0, le=5)

    # Uploaded CSV / Excel files, total per upload. Vercel rejects request bodies over 4.5 MB.
    max_upload_mb: float = Field(default=4.0, gt=0)

    # Conversation context sent to the LLM
    context_turns: int = Field(default=4, ge=0, le=20)
    schema_table_budget: int = Field(default=12, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
