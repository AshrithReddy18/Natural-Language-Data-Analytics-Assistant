"""Data-source abstraction: what the rest of the app needs from a database it analyses."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False
    references: str | None = None  # "table.column" for a foreign key
    # Hints that help the model write correct filters. Only collected for low-cardinality
    # text columns and date/time columns; never for free text or identifiers.
    sample_values: list[str] | None = None
    value_range: tuple[str, str] | None = None


@dataclass(frozen=True)
class TableInfo:
    name: str
    columns: list[ColumnInfo]
    row_count: int | None = None


@dataclass(frozen=True)
class Relationship:
    from_table: str
    from_column: str
    to_table: str
    to_column: str


@dataclass
class SchemaSnapshot:
    dialect: str  # sqlglot dialect name, e.g. "postgres"
    tables: list[TableInfo]
    relationships: list[Relationship] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def table(self, name: str) -> TableInfo | None:
        lowered = name.lower()
        return next((t for t in self.tables if t.name.lower() == lowered), None)

    def as_sqlglot_schema(self) -> dict[str, dict[str, str]]:
        return {t.name: {c.name: c.type for c in t.columns} for t in self.tables}


@dataclass(frozen=True)
class RawResult:
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool
    elapsed_ms: int


class Connector(Protocol):
    kind: str
    dialect: str  # sqlglot dialect
    dialect_label: str  # human-readable, used in prompts

    def test_connection(self) -> None: ...

    def introspect(self) -> SchemaSnapshot: ...

    def execute_readonly(self, sql: str, *, max_rows: int, timeout_s: float) -> RawResult: ...

    def dispose(self) -> None: ...
