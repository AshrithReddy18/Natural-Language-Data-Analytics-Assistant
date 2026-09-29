"""Builds the configured LLM provider. Switching vendors is a configuration change only."""

import os
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.core.errors import LLMNotConfiguredError
from app.llm.base import LLMProvider


def llm_status(settings: Settings | None = None) -> tuple[bool, str, str | None]:
    """(configured, provider name, model) without making a network call."""
    s = settings or get_settings()
    if s.llm_provider == "anthropic":
        has_key = bool(s.anthropic_api_key) or any(
            os.environ.get(v) for v in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
        )
        from app.llm.providers.anthropic_provider import DEFAULT_MODEL

        return has_key, "anthropic", s.llm_model or DEFAULT_MODEL
    if s.llm_provider == "openai":
        has_key = bool(s.openai_api_key) or bool(os.environ.get("OPENAI_API_KEY"))
        from app.llm.providers.openai_provider import DEFAULT_MODEL as OPENAI_DEFAULT

        return has_key, "openai", s.llm_model or OPENAI_DEFAULT
    return False, "none", None


@lru_cache
def get_llm_provider() -> LLMProvider:
    s = get_settings()
    configured, name, model = llm_status(s)
    if not configured:
        raise LLMNotConfiguredError()
    if name == "anthropic":
        from app.llm.providers.anthropic_provider import AnthropicProvider

        key = s.anthropic_api_key.get_secret_value() if s.anthropic_api_key else None
        return AnthropicProvider(
            api_key=key, model=model, timeout=s.llm_timeout_seconds, fallbacks=s.anthropic_fallbacks
        )
    from app.llm.providers.openai_provider import OpenAIProvider

    key = s.openai_api_key.get_secret_value() if s.openai_api_key else None
    return OpenAIProvider(api_key=key, model=model, timeout=s.llm_timeout_seconds)
