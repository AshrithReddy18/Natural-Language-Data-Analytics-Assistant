"""OpenAI via the official SDK, using Pydantic-typed structured outputs."""

import logging

import openai
from openai.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError

from app.core.errors import LLMOutputError, LLMUnavailableError
from app.core.logging import log_event
from app.llm.base import ChatTurn, Effort, T

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4.1"


class OpenAIProvider:
    name = "openai"

    def __init__(self, *, api_key: str | None, model: str | None, timeout: float) -> None:
        self.model = model or DEFAULT_MODEL
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=2)

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
        try:
            completion = self._client.chat.completions.parse(
                model=self.model,
                max_completion_tokens=max_tokens,
                messages=chat,
                response_format=output_type,
            )
        except openai.AuthenticationError as exc:
            raise LLMUnavailableError("The AI provider rejected the API key.") from exc
        except openai.RateLimitError as exc:
            raise LLMUnavailableError("The AI provider is rate limiting requests. Try again shortly.") from exc
        except openai.APITimeoutError as exc:
            raise LLMUnavailableError("The AI provider took too long to respond.") from exc
        except openai.BadRequestError as exc:
            raise LLMOutputError("The AI request was rejected by the provider.") from exc
        except openai.APIStatusError as exc:
            raise LLMUnavailableError(f"The AI provider returned an error ({exc.status_code}).") from exc
        except openai.APIConnectionError as exc:
            raise LLMUnavailableError("Could not reach the AI provider.") from exc
        except (ValidationError, openai.LengthFinishReasonError, openai.ContentFilterFinishReasonError) as exc:
            raise LLMOutputError(detail=str(exc)) from exc

        choice = completion.choices[0]
        log_event(
            logger,
            "llm_call",
            provider=self.name,
            model=completion.model,
            output_type=output_type.__name__,
            finish_reason=choice.finish_reason,
        )
        if choice.message.refusal:
            raise LLMOutputError("The AI model declined to answer this request.")
        if choice.message.parsed is None:
            raise LLMOutputError()
        return choice.message.parsed
