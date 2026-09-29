"""Builds the configured LLM provider. Switching vendors is a configuration change only.

Providers:
  anthropic  Claude via the Anthropic SDK (paid API key)
  openai     OpenAI (paid API key)
  gemini     Google Gemini through its OpenAI-compatible endpoint (free-tier key from AI Studio)
  ollama     A local model served by Ollama (free, runs on your machine, no key)
"""

import os
from dataclasses import dataclass
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.core.errors import LLMNotConfiguredError
from app.llm.base import LLMProvider


@dataclass(frozen=True)
class CompatiblePreset:
    base_url: str
    default_model: str
    key_env: str | None  # environment variable holding the key; None = no key needed


PRESETS = {
    "gemini": CompatiblePreset(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        default_model="gemini-3.8-flash",
        key_env="GEMINI_API_KEY",
    ),
    "ollama": CompatiblePreset(
        base_url="http://localhost:11434/v1",
        default_model="qwen2.5-coder:7b",
        key_env=None,
    ),
}


def _secret(value: object) -> str | None:
    getter = getattr(value, "get_secret_value", None)
    return getter() if getter else None


def llm_status(settings: Settings | None = None) -> tuple[bool, str, str | None]:
    """(configured, provider name, model) without making a network call."""
    s = settings or get_settings()
    provider = s.llm_provider
    if provider == "anthropic":
        has_key = bool(s.anthropic_api_key) or any(
            os.environ.get(v) for v in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
        )
        from app.llm.providers.anthropic_provider import DEFAULT_MODEL

        return has_key, provider, s.llm_model or DEFAULT_MODEL
    if provider == "openai":
        has_key = bool(s.openai_api_key) or bool(os.environ.get("OPENAI_API_KEY"))
        from app.llm.providers.openai_provider import DEFAULT_MODEL as OPENAI_DEFAULT

        return has_key, provider, s.llm_model or OPENAI_DEFAULT
    if provider in PRESETS:
        preset = PRESETS[provider]
        has_key = preset.key_env is None or bool(_secret(s.gemini_api_key) or os.environ.get(preset.key_env))
        return has_key, provider, s.llm_model or preset.default_model
    return False, "none", None


@lru_cache
def get_llm_provider() -> LLMProvider:
    s = get_settings()
    configured, name, model = llm_status(s)
    if not configured:
        raise LLMNotConfiguredError()
    if name == "anthropic":
        from app.llm.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=_secret(s.anthropic_api_key), model=model, timeout=s.llm_timeout_seconds,
            fallbacks=s.anthropic_fallbacks,
        )  # fmt: skip

    from app.llm.providers.openai_provider import OpenAIProvider

    if name == "openai":
        return OpenAIProvider(
            api_key=_secret(s.openai_api_key), model=model, timeout=s.llm_timeout_seconds, base_url=s.llm_base_url
        )
    preset = PRESETS[name]
    base_url = s.llm_base_url or preset.base_url
    if name == "ollama":
        return OpenAIProvider(
            api_key="ollama",  # required by the SDK, ignored by Ollama
            model=model,
            timeout=max(s.llm_timeout_seconds, 180),  # the first request loads the model into memory
            base_url=base_url,
            name=name,
            unreachable_hint=f"Could not reach Ollama at {base_url}. Is Ollama running (`ollama serve`)?",
        )
    key = _secret(s.gemini_api_key) or os.environ.get(preset.key_env or "")
    return OpenAIProvider(api_key=key, model=model, timeout=s.llm_timeout_seconds, base_url=base_url, name=name)
