"""A scripted LLM provider so the pipeline can be tested deterministically and offline."""

from dataclasses import dataclass, field
from typing import Any

from app.core.errors import LLMUnavailableError
from app.llm.base import ChatTurn
from app.schemas.llm_outputs import InsightText, SQLPlan


def plan(sql: str | None = None, **overrides: Any) -> SQLPlan:
    base: dict[str, Any] = {
        "status": "answer",
        "intent": "test_intent",
        "interpretation": "Test interpretation.",
        "title": "Test result",
        "sql": sql,
        "reasoning_summary": "Test reasoning.",
    }
    base.update(overrides)
    return SQLPlan(**base)


@dataclass
class Call:
    system: str
    messages: list[ChatTurn]
    output_type: type


@dataclass
class FakeProvider:
    plans: list[SQLPlan | Exception] = field(default_factory=list)
    insight: InsightText | Exception | None = None
    calls: list[Call] = field(default_factory=list)
    name: str = "fake"
    model: str = "fake-model"

    def generate_structured(self, *, system: str, messages: list[ChatTurn], output_type: type, **_: Any) -> Any:
        self.calls.append(Call(system, list(messages), output_type))
        if output_type is SQLPlan:
            if not self.plans:
                raise AssertionError("FakeProvider ran out of scripted plans")
            item = self.plans.pop(0)
        else:
            item = self.insight if self.insight is not None else LLMUnavailableError()
        if isinstance(item, Exception):
            raise item
        return item

    @property
    def sql_calls(self) -> list[Call]:
        return [c for c in self.calls if c.output_type is SQLPlan]
