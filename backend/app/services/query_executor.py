"""Executes validated SQL and normalises results into JSON-safe values."""

import logging
import math
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.logging import log_event
from app.datasources.base import Connector
from app.schemas.analysis import QueryResultData
from app.services.result_analyzer import profile_columns
from app.services.sql_validator import ValidationResult

logger = logging.getLogger(__name__)


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal):
        f = float(value)
        return int(f) if value == value.to_integral_value() and abs(f) < 2**53 else f
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"<{len(bytes(value))} bytes>"
    return str(value)


class QueryExecutor:
    def __init__(self, connector: Connector, *, timeout_s: float, max_rows: int) -> None:
        self.connector = connector
        self.timeout_s = timeout_s
        self.max_rows = max_rows

    def execute(self, validation: ValidationResult) -> QueryResultData:
        """Only accepts a successful ValidationResult: unvalidated SQL has no path to the DB."""
        if not validation.ok or not validation.validated_sql:
            raise ValueError("Refusing to execute SQL that has not passed validation")
        raw = self.connector.execute_readonly(
            validation.validated_sql, max_rows=self.max_rows, timeout_s=self.timeout_s
        )
        rows = [[_jsonable(v) for v in row] for row in raw.rows]
        # With an enforced LIMIT equal to max_rows, hitting it means there may be more rows.
        truncated = raw.truncated or (validation.limit_applied is not None and len(rows) >= validation.limit_applied)
        log_event(
            logger,
            "query_executed",
            row_count=len(rows),
            execution_ms=raw.elapsed_ms,
            truncated=truncated,
            tables=validation.tables,
        )
        return QueryResultData(
            columns=profile_columns(raw.columns, rows),
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            execution_ms=raw.elapsed_ms,
        )
