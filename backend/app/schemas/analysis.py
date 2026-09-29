"""The analysis contract: what one answered question looks like end to end."""

from typing import Any, Literal

from pydantic import BaseModel, Field

ColumnKind = Literal["temporal", "numeric", "categorical", "identifier", "boolean", "text"]
ValueFormat = Literal["currency", "percent", "number", "integer", "text", "date"]
ChartType = Literal["line", "bar", "horizontal_bar", "donut", "scatter", "kpi", "table"]


class ColumnMeta(BaseModel):
    name: str
    kind: ColumnKind
    format: ValueFormat
    distinct_count: int
    null_count: int = 0


class QueryResultData(BaseModel):
    columns: list[ColumnMeta]
    rows: list[list[Any]]
    row_count: int
    truncated: bool = False
    execution_ms: int


class ValidationInfo(BaseModel):
    ok: bool
    errors: list[str] = []
    warnings: list[str] = []
    limit_applied: int | None = None
    tables: list[str] = []


class SQLAttempt(BaseModel):
    """One generate→validate→execute attempt; failed attempts are kept for transparency."""

    sql: str
    stage: Literal["validation", "execution", "success"]
    error: str | None = None


class SQLInfo(BaseModel):
    dialect: str
    generated_sql: str
    validated_sql: str | None = None
    validation: ValidationInfo
    attempts: list[SQLAttempt] = []


class ChartSpec(BaseModel):
    type: ChartType
    x: str | None = None
    y: list[str] = []
    series: str | None = None
    title: str = ""
    reason: str = ""
    max_points: int | None = None


class Kpi(BaseModel):
    label: str
    value: float | int | str
    format: ValueFormat = "number"
    delta_pct: float | None = None
    delta_label: str | None = None


class Insight(BaseModel):
    headline: str
    bullets: list[str] = []
    facts: list[str] = Field(default=[], description="Deterministic facts the text is based on")
    generated_by: Literal["llm", "rules"] = "rules"


class Clarification(BaseModel):
    question: str
    options: list[str] = []


class ErrorInfo(BaseModel):
    code: str
    message: str


AnalysisStatus = Literal["success", "empty", "clarification", "unanswerable", "error"]


class AnalysisResult(BaseModel):
    status: AnalysisStatus
    question: str
    interpretation: str | None = None
    title: str | None = None
    reasoning_summary: str | None = None
    sql: SQLInfo | None = None
    result: QueryResultData | None = None
    chart: ChartSpec | None = None
    kpis: list[Kpi] = []
    insight: Insight | None = None
    clarification: Clarification | None = None
    error: ErrorInfo | None = None
    query_run_id: str | None = None
    currency: str = "INR"
