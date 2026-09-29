"""Any OpenAI-compatible chat API via the official OpenAI SDK: OpenAI itself, Google Gemini's
OpenAI endpoint, or a local Ollama server. Uses Pydantic-typed structured outputs, falling back
to plain JSON mode for servers that reject strict JSON schemas."""

import json
import logging
import re

import openai
from openai.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError

from app.core.errors import LLMOutputError, LLMUnavailableError
from app.core.logging import log_event
from app.llm.base import ChatTurn, Effort, T

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4.1"

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.I)


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
    ) -> None:
        self.name = name
        self.model = model or DEFAULT_MODEL
        self._unreachable_hint = unreachable_hint
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=2)

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
            try:
                return self._parse(chat, output_type, max_tokens)
            except openai.BadRequestError as exc:
                # Some compatible servers don't accept strict json_schema response formats.
                log_event(logger, "llm_json_schema_unsupported", logging.WARNING, provider=self.name, error=exc.message)
                return self._json_mode(chat, output_type, max_tokens)
        except openai.AuthenticationError as exc:
            raise LLMUnavailableError("The AI provider rejected the API key.") from exc
        except openai.RateLimitError as exc:
            raise LLMUnavailableError("The AI provider is rate limiting requests. Try again shortly.") from exc
        except openai.APITimeoutError as exc:
            raise LLMUnavailableError("The AI provider took too long to respond.") from exc
        except openai.NotFoundError as exc:
            raise LLMUnavailableError(f"The model '{self.model}' was not found at the AI provider.") from exc
        except openai.BadRequestError as exc:
            raise LLMOutputError("The AI request was rejected by the provider.") from exc
        except openai.APIStatusError as exc:
            raise LLMUnavailableError(f"The AI provider returned an error ({exc.status_code}).") from exc
        except openai.APIConnectionError as exc:
            raise LLMUnavailableError(self._unreachable_hint) from exc
        except (ValidationError, openai.LengthFinishReasonError, openai.ContentFilterFinishReasonError) as exc:
            raise LLMOutputError(detail=str(exc)) from exc

    def _parse(self, chat: list[ChatCompletionMessageParam], output_type: type[T], max_tokens: int) -> T:
        completion = self._client.chat.completions.parse(
            model=self.model, max_completion_tokens=max_tokens, messages=chat, response_format=output_type
        )
        choice = completion.choices[0]
        log_event(logger, "llm_call", provider=self.name, model=completion.model,
                  output_type=output_type.__name__, finish_reason=choice.finish_reason)  # fmt: skip
        if choice.message.refusal:
            raise LLMOutputError("The AI model declined to answer this request.")
        if choice.message.parsed is None:
            raise LLMOutputError()
        return choice.message.parsed

    def _json_mode(self, chat: list[ChatCompletionMessageParam], output_type: type[T], max_tokens: int) -> T:
        schema = json.dumps(output_type.model_json_schema())
        instruction = f"\n\nRespond with a single JSON object (no markdown) that matches this JSON schema:\n{schema}"
        first = chat[0]
        with_schema: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": str(first.get("content", "")) + instruction},
            *chat[1:],
        ]
        completion = self._client.chat.completions.create(
            model=self.model, max_tokens=max_tokens, messages=with_schema, response_format={"type": "json_object"}
        )
        text = completion.choices[0].message.content or ""
        log_event(logger, "llm_call", provider=self.name, model=completion.model, output_type=output_type.__name__,
                  finish_reason=completion.choices[0].finish_reason, mode="json_object")  # fmt: skip
        return output_type.model_validate_json(_FENCE.sub("", text))
