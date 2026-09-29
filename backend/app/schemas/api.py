"""REST request/response models."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.analysis import AnalysisResult, ValidationInfo


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: bool
    llm_configured: bool
    llm_provider: str
    llm_model: str | None


# -- data sources ----------------------------------------------------------------------------


class DataSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=2000, description="SQLAlchemy URL, e.g. postgresql://user:pw@host/db")
    description: str | None = Field(default=None, max_length=1000)
    business_notes: str | None = Field(default=None, max_length=4000)
    currency: str = Field(default="INR", min_length=3, max_length=3)


class DataSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    business_notes: str | None = Field(default=None, max_length=4000)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class DataSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    kind: str
    display_url: str
    description: str | None
    business_notes: str | None
    currency: str
    is_demo: bool
    created_at: datetime
    status: Literal["connected", "error", "unknown"] = "unknown"
    status_message: str | None = None
    table_count: int | None = None


class ColumnOut(BaseModel):
    name: str
    type: str
    nullable: bool
    primary_key: bool
    references: str | None
    sample_values: list[str] | None
    value_range: list[str] | None


class TableOut(BaseModel):
    name: str
    row_count: int | None
    columns: list[ColumnOut]


class RelationshipOut(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str


class SchemaOut(BaseModel):
    data_source_id: str
    dialect: str
    tables: list[TableOut]
    relationships: list[RelationshipOut]
    fetched_at: datetime


# -- chat ------------------------------------------------------------------------------------


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    data_source_id: str
    conversation_id: str | None = None


class MessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    analysis: AnalysisResult | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    user_message: MessageOut
    assistant_message: MessageOut


class ConversationSummary(BaseModel):
    id: str
    title: str
    data_source_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class ConversationDetail(ConversationSummary):
    messages: list[MessageOut]


# -- SQL workbench / query history -----------------------------------------------------------


class QueryRequest(BaseModel):
    data_source_id: str
    sql: str = Field(min_length=1, max_length=20_000)


class QueryValidateResponse(BaseModel):
    validated_sql: str | None
    validation: ValidationInfo


class QueryRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    data_source_id: str
    conversation_id: str | None
    message_id: str | None
    source: str
    question: str | None
    generated_sql: str | None
    validated_sql: str | None
    status: str
    error_message: str | None
    row_count: int | None
    execution_ms: int | None
    attempts: int
    created_at: datetime


class ErrorResponse(BaseModel):
    error: dict[str, Any]
