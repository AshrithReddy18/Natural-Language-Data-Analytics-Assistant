"""Provider-neutral LLM interface. Services depend on this, never on a vendor SDK."""

from dataclasses import dataclass
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

Effort = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ChatTurn:
    role: Literal["user", "assistant"]
    content: str


class LLMProvider(Protocol):
    name: str
    model: str

    def generate_structured(
        self,
        *,
        system: str,
        messages: list[ChatTurn],
        output_type: type[T],
        effort: Effort = "medium",
        max_tokens: int = 8000,
    ) -> T:
        """Return a validated instance of `output_type`.

        Raises LLMUnavailableError for transport/auth/rate-limit problems and LLMOutputError when
        the model's response cannot be used (refusal, truncation, schema mismatch).
        """
        ...
