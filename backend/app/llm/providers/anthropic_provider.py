"""Claude via the official Anthropic SDK, using JSON-schema structured outputs."""

import logging

import anthropic
from pydantic import ValidationError

from app.core.errors import LLMOutputError, LLMUnavailableError
from app.core.logging import log_event
from app.llm.base import ChatTurn, Effort, T

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
# Server-side refusal fallback: if the primary model declines, the API re-runs the request on a
# suitable fallback model within the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, *, api_key: str | None, model: str | None, timeout: float, fallbacks: bool) -> None:
        self.model = model or DEFAULT_MODEL
        self._fallbacks = fallbacks
        # api_key=None lets the SDK resolve ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / profiles.
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)

    def generate_structured(
        self,
        *,
        system: str,
        messages: list[ChatTurn],
        output_type: type[T],
        effort: Effort = "medium",
        max_tokens: int = 8000,
    ) -> T:
        extra: dict[str, object] = {}
        if self._fallbacks:
            extra = {"betas": [FALLBACK_BETA], "fallbacks": "default"}
        try:
            response = self._client.beta.messages.parse(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                output_format=output_type,
                output_config={"effort": effort},
                **extra,  # type: ignore[arg-type]
            )
        except anthropic.AuthenticationError as exc:
            raise LLMUnavailableError("The AI provider rejected the API key.") from exc
        except anthropic.RateLimitError as exc:
            raise LLMUnavailableError("The AI provider is rate limiting requests. Try again shortly.") from exc
        except anthropic.APITimeoutError as exc:
            raise LLMUnavailableError("The AI provider took too long to respond.") from exc
        except anthropic.BadRequestError as exc:
            log_event(logger, "llm_bad_request", logging.ERROR, provider=self.name, error=exc.message)
            raise LLMOutputError("The AI request was rejected by the provider.") from exc
        except anthropic.APIStatusError as exc:
            raise LLMUnavailableError(f"The AI provider returned an error ({exc.status_code}).") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMUnavailableError("Could not reach the AI provider.") from exc
        except ValidationError as exc:
            raise LLMOutputError(detail=str(exc)) from exc

        usage = response.usage
        log_event(
            logger,
            "llm_call",
            provider=self.name,
            model=response.model,
            output_type=output_type.__name__,
            stop_reason=response.stop_reason,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        if response.stop_reason == "refusal":
            raise LLMOutputError("The AI model declined to answer this request.")
        if response.stop_reason == "max_tokens":
            raise LLMOutputError("The AI response was cut off before it finished.")
        parsed = response.parsed_output
        if parsed is None:
            raise LLMOutputError()
        return parsed
