"""Structured outputs requested from the LLM. Validated with Pydantic before use."""

from typing import Literal

from pydantic import BaseModel, Field


class SQLPlan(BaseModel):
    """The model's plan for answering one question."""

    status: Literal["answer", "clarify", "unanswerable"] = Field(
        description=(
            "'answer' when a SQL query can answer the question; 'clarify' when the question is "
            "materially ambiguous; 'unanswerable' when the schema has no data for it."
        )
    )
    intent: str = Field(description="Short snake_case label, e.g. revenue_by_city")
    interpretation: str = Field(
        description="One sentence restating the question as understood, including any assumption made"
    )
    title: str = Field(description="Short title for the result, e.g. 'Revenue by city, 2025'")
    sql: str | None = Field(default=None, description="A single read-only SELECT query, or null")
    tables_used: list[str] = []
    dimensions: list[str] = Field(default=[], description="Output columns used to group/label")
    measures: list[str] = Field(default=[], description="Output columns holding metrics")
    chart_hint: Literal["auto", "line", "bar", "horizontal_bar", "donut", "scatter", "kpi", "table"] = "auto"
    clarification_question: str | None = None
    clarification_options: list[str] = []
    reasoning_summary: str = Field(description="One or two sentences on how the query answers it")


class InsightText(BaseModel):
    headline: str = Field(description="One sentence with the single most important finding")
    bullets: list[str] = Field(description="Up to three short supporting observations")
