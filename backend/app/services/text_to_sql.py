"""Turns a question (plus bounded conversation context) into a structured SQL plan."""

import json
from dataclasses import dataclass, field
from datetime import date

from app.llm.base import ChatTurn, LLMProvider
from app.schemas.llm_outputs import SQLPlan

SYSTEM_TEMPLATE = """You are DataPilot, a careful senior data analyst who writes {dialect} SQL.

Your job: turn the user's question into ONE read-only SQL query against the database below,
and describe how it answers the question. You never see query results in this step.

Rules
1. Use only tables and columns that appear in the schema. Never invent columns.
2. Produce a single SELECT statement (CTEs allowed). Never modify data or schema.
3. Write {dialect} syntax.{dialect_notes}
4. Give every computed column a readable snake_case alias (e.g. total_revenue, order_count).
5. Put the grouping/label column(s) first and the metric column(s) after them.
6. Round monetary values and ratios to 2 decimals; express percentages as 0–100.
7. Order results meaningfully: chronologically for time series, descending by the main metric
   for rankings. Add LIMIT for "top N" questions. For "which X is highest/lowest" questions return
   a ranked list with LIMIT 10 (not a single row) so the answer shows context. Otherwise do not
   add a LIMIT.
8. Time: today's date is {today}. The most recent data is from {latest_date}. When the user says
   "this year", "last month", "recent" etc., anchor to the most recent data rather than today,
   and state that assumption in `interpretation`. Only use dates inside the ranges shown in the
   schema: never compare against a period that has no data.
9. Comparisons across years: return one row per period within the year (e.g. month number 1–12)
   with one column per year (revenue_2024, revenue_2025), or add a year column. Never return one
   row per year-month with zero-filled columns for the other year.
10. Trends such as "declining" or "growing" compare the two most recent complete periods in the
   data (e.g. the last two years) and include the change (difference or percent).
11. Follow-up questions refer to earlier turns ("which month was highest?", "compare it with the
   previous year"). Reuse the earlier query's logic and filters unless the user changes them.
   Do not ask for clarification when an earlier turn already establishes what is meant. Keep
   the SQL simple: prefer a CTE for the earlier result over nested aggregate subqueries.
12. Choose status:
    - "answer" (the default): pick the most reasonable reading and state any assumption in
      `interpretation`.
    - "clarify": only if the question is genuinely ambiguous AND the readings would give
      materially different answers AND no sensible default exists. Offer 2–4 options.
    - "unanswerable": the schema has no data that could answer it. Explain in `interpretation`.
13. `measures` and `dimensions` must use the exact output column aliases of your query.
{business_notes}
Database schema
{schema}"""

DIALECT_NOTES = {
    "postgres": (
        " Use date_trunc('month', col) / EXTRACT(YEAR FROM col) for dates, ILIKE for "
        "case-insensitive matching, and cast to numeric before ROUND(x::numeric, 2)."
    ),
    "sqlite": (
        " Use strftime('%Y-%m', col) for months and CAST(strftime('%Y', col) AS INTEGER) for years; "
        "there is no date_trunc or EXTRACT. Multiply by 1.0 before dividing integers."
    ),
}

REPAIR_TEMPLATE = """The query you wrote failed during {stage}:

{error}

Return a corrected plan. Keep the same intent; fix only what is wrong. Use only columns and
tables from the schema."""


@dataclass
class PriorTurn:
    """A compact summary of an earlier exchange, used as conversation context."""

    question: str
    interpretation: str | None = None
    sql: str | None = None
    columns: list[str] = field(default_factory=list)
    row_count: int | None = None
    sample_rows: list[list[object]] = field(default_factory=list)
    note: str | None = None

    def as_assistant_text(self) -> str:
        parts = []
        if self.interpretation:
            parts.append(f"Interpretation: {self.interpretation}")
        if self.sql:
            parts.append(f"SQL:\n{self.sql}")
        if self.columns:
            parts.append(f"Result columns: {', '.join(self.columns)}; {self.row_count} rows.")
        if self.sample_rows:
            parts.append("First rows: " + json.dumps(self.sample_rows, default=str))
        if self.note:
            parts.append(self.note)
        return "\n".join(parts) or "(no result)"


@dataclass
class FailedAttempt:
    plan: SQLPlan
    stage: str
    error: str


class TextToSQLService:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def build_system_prompt(
        self,
        *,
        dialect: str,
        dialect_label: str,
        schema_text: str,
        latest_date: str | None,
        business_notes: str | None,
    ) -> str:
        notes = ""
        if business_notes and business_notes.strip():
            notes = f"\nBusiness definitions for this database (follow them):\n{business_notes.strip()}\n"
        return SYSTEM_TEMPLATE.format(
            dialect=dialect_label,
            dialect_notes=DIALECT_NOTES.get(dialect, ""),
            today=date.today().isoformat(),
            latest_date=latest_date or "unknown",
            business_notes=notes,
            schema=schema_text,
        )

    def generate(
        self,
        *,
        system_prompt: str,
        question: str,
        history: list[PriorTurn],
        failures: list[FailedAttempt] | None = None,
    ) -> SQLPlan:
        messages: list[ChatTurn] = []
        for turn in history:
            messages.append(ChatTurn("user", turn.question))
            messages.append(ChatTurn("assistant", turn.as_assistant_text()))
        messages.append(ChatTurn("user", question))
        for failure in failures or []:
            messages.append(ChatTurn("assistant", failure.plan.model_dump_json(exclude_none=True)))
            messages.append(ChatTurn("user", REPAIR_TEMPLATE.format(stage=failure.stage, error=failure.error)))
        return self.provider.generate_structured(
            system=system_prompt,
            messages=messages,
            output_type=SQLPlan,
            effort="medium",
        )
