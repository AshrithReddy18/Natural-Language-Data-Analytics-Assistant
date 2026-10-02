"""Any OpenAI-compatible chat API via the official OpenAI SDK: OpenAI itself, Google Gemini's
OpenAI endpoint, or a local Ollama server. Uses Pydantic-typed structured outputs, falling back
to plain JSON mode for servers that reject strict JSON schemas.

When the model is overloaded or rate limited, the request moves on to the configured fallback
models (on Gemini's free tier each model has its own quota). A model that just failed that way is
skipped for a short cooldown, so later requests don't wait for it to fail again."""

import json
import logging
import re
import threading
import time
from collections.abc import Sequence

import openai
from openai.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError

from app.core.errors import LLMOutputError, LLMUnavailableError
from app.core.logging import log_event
from app.llm.base import ChatTurn, Effort, T

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4.1"

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.I)
COOLDOWN_SECONDS = 60.0

# Errors that mean "this model can't take the request right now", as opposed to a bad request.
_BUSY = (openai.RateLimitError, openai.InternalServerError, openai.APITimeoutError)


class OpenAIProvider:
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str | None,
        timeout: float,
        base_url: str | None = None,
        name: str = "openai",
        unreachable_hint: str = "Could not reach the AI provider.",
        fallback_models: Sequence[str] = (),
    ) -> None:
        self.name = name
        self.model = model or DEFAULT_MODEL
        self.fallback_models = [m for m in dict.fromkeys(fallback_models) if m != self.model]
        self._unreachable_hint = unreachable_hint
        # With fallbacks, move on to the next model at once: an overloaded model is rarely free a
        # second later, and the SDK's retry backoff would add many seconds per busy model.
        retries = 0 if self.fallback_models else 2
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=retries)
        self._busy_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def _candidates(self) -> list[str]:
        """Models to try in order: those not cooling down first, then the rest as a last resort."""
        now = time.monotonic()
        with self._lock:
            models = [self.model, *self.fallback_models]
            ready = [m for m in models if self._busy_until.get(m, 0) <= now]
        return ready + [m for m in models if m not in ready]

    def _mark_busy(self, model: str) -> None:
        with self._lock:
            self._busy_until[model] = time.monotonic() + COOLDOWN_SECONDS

    def generate_structured(
        self,
        *,
        system: str,
        messages: list[ChatTurn],
        output_type: type[T],
        effort: Effort = "medium",
        max_tokens: int = 8000,
    ) -> T:
        chat: list[ChatCompletionMessageParam] = [{"role": "system", "content": system}]
        for m in messages:
            if m.role == "user":
                chat.append({"role": "user", "content": m.content})
            else:
                chat.append({"role": "assistant", "content": m.content})
        candidates = self._candidates()
        for i, model in enumerate(candidates):
            try:
                return self._generate(model, chat, output_type, max_tokens)
            except _BUSY as exc:
                self._mark_busy(model)
                last = i == len(candidates) - 1
                log_event(
                    logger, "llm_model_busy", logging.WARNING, provider=self.name, model=model,
                    error=_describe(exc), next_model=None if last else candidates[i + 1],
                )  # fmt: skip
                if last:
                    raise self._public_error(exc) from exc
            except Exception as exc:
                if isinstance(exc, openai.APIError):
                    log_event(
                        logger, "llm_error", logging.WARNING, provider=self.name, model=model, error=_describe(exc)
                    )
                raise self._public_error(exc) from exc
        raise AssertionError("unreachable: there is always at least one model")

    def _generate(self, model: str, chat: list[ChatCompletionMessageParam], output_type: type[T], max_tokens: int) -> T:
        try:
            return self._parse(model, chat, output_type, max_tokens)
        except openai.BadRequestError as exc:
            # Some compatible servers don't accept strict json_schema response formats.
            log_event(logger, "llm_json_schema_unsupported", logging.WARNING, provider=self.name, error=exc.message)
            return self._json_mode(model, chat, output_type, max_tokens)

    def _public_error(self, exc: Exception) -> Exception:
        """Translate an SDK error into a user-safe application error."""
        if isinstance(exc, openai.AuthenticationError):
            return LLMUnavailableError("The AI provider rejected the API key.")
        if isinstance(exc, openai.RateLimitError):
            return LLMUnavailableError("The AI provider is rate limiting requests. Try again shortly.")
        if isinstance(exc, openai.APITimeoutError):
            return LLMUnavailableError("The AI provider took too long to respond.")
        if isinstance(exc, openai.NotFoundError):
            return LLMUnavailableError(f"The model '{self.model}' was not found at the AI provider.")
        if isinstance(exc, openai.BadRequestError):
            return LLMOutputError("The AI request was rejected by the provider.")
        if isinstance(exc, openai.InternalServerError):
            return LLMUnavailableError("The AI model is overloaded right now. Try again in a minute.")
        if isinstance(exc, openai.APIStatusError):
            return LLMUnavailableError(f"The AI provider returned an error ({exc.status_code}).")
        if isinstance(exc, openai.APIConnectionError):
            return LLMUnavailableError(self._unreachable_hint)
        if isinstance(exc, ValidationError | openai.LengthFinishReasonError | openai.ContentFilterFinishReasonError):
            return LLMOutputError(detail=str(exc))
        return exc

    def _parse(self, model: str, chat: list[ChatCompletionMessageParam], output_type: type[T], max_tokens: int) -> T:
        completion = self._client.chat.completions.parse(
            model=model, max_completion_tokens=max_tokens, messages=chat, response_format=output_type
        )
        choice = completion.choices[0]
        log_event(logger, "llm_call", provider=self.name, model=completion.model,
                  output_type=output_type.__name__, finish_reason=choice.finish_reason)  # fmt: skip
        if choice.message.refusal:
            raise LLMOutputError("The AI model declined to answer this request.")
        if choice.message.parsed is None:
            raise LLMOutputError()
        return choice.message.parsed

    def _json_mode(
        self, model: str, chat: list[ChatCompletionMessageParam], output_type: type[T], max_tokens: int
    ) -> T:
        schema = json.dumps(output_type.model_json_schema())
        instruction = f"\n\nRespond with a single JSON object (no markdown) that matches this JSON schema:\n{schema}"
        first = chat[0]
        with_schema: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": str(first.get("content", "")) + instruction},
            *chat[1:],
        ]
        completion = self._client.chat.completions.create(
            model=model, max_tokens=max_tokens, messages=with_schema, response_format={"type": "json_object"}
        )
        text = completion.choices[0].message.content or ""
        log_event(logger, "llm_call", provider=self.name, model=completion.model, output_type=output_type.__name__,
                  finish_reason=completion.choices[0].finish_reason, mode="json_object")  # fmt: skip
        return output_type.model_validate_json(_FENCE.sub("", text))


def _describe(exc: Exception) -> str:
    """A short description of a provider error for logs (no request content or keys)."""
    status = getattr(exc, "status_code", None)
    message = getattr(exc, "message", None) or str(exc)
    return f"{status} {message}"[:300] if status else message[:300]
