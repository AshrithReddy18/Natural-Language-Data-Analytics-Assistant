"""A SQLAlchemy-backed connector covering PostgreSQL and SQLite.

Adding MySQL etc. later means adding a dialect branch for read-only enforcement and timeouts;
everything above this layer (validation, execution service, pipeline) is dialect-agnostic.
"""

import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, column, create_engine, func, inspect, select, table, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError

from app.core.errors import DataSourceUnavailableError, QueryExecutionError, QueryTimeoutError
from app.datasources.base import ColumnInfo, RawResult, Relationship, SchemaSnapshot, TableInfo

logger = logging.getLogger(__name__)

_TEXT_TYPES = ("CHAR", "TEXT", "STRING", "VARCHAR")
_TEMPORAL_TYPES = ("DATE", "TIME")
# Never sample values from columns that look like personal data or secrets.
_SENSITIVE = re.compile(r"(email|phone|password|passwd|secret|token|address|ssn|card|iban|name$)", re.I)
_MAX_SAMPLE_DISTINCT = 12
_MAX_ROWS_FOR_PROFILING = 2_000_000


class SQLAlchemyConnector:
    def __init__(self, url: str) -> None:
        parsed = make_url(url)
        backend = parsed.get_backend_name()
        if backend == "postgresql":
            self.kind, self.dialect, self.dialect_label = "postgresql", "postgres", "PostgreSQL"
            if parsed.drivername == "postgresql":
                parsed = parsed.set(drivername="postgresql+psycopg")
            self._engine: Engine = create_engine(
                parsed,
                pool_pre_ping=True,
                pool_size=3,
                max_overflow=2,
                connect_args={"connect_timeout": 5},
            )
        elif backend == "sqlite":
            self.kind, self.dialect, self.dialect_label = "sqlite", "sqlite", "SQLite"
            db_path = Path(parsed.database or "")
            if not db_path.is_file():
                raise DataSourceUnavailableError(f"SQLite database file not found: {db_path.name}")
            uri = db_path.resolve().as_uri() + "?mode=ro"
            # Opened read-only at the driver level: writes fail even if validation were bypassed.
            self._engine = create_engine(
                "sqlite://",
                creator=lambda: sqlite3.connect(uri, uri=True, check_same_thread=False),
            )
        else:
            raise ValueError(f"Unsupported database type: {backend}")

    # -- connectivity -----------------------------------------------------------------------

    def test_connection(self) -> None:
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise DataSourceUnavailableError(detail=type(exc).__name__) from exc

    def dispose(self) -> None:
        self._engine.dispose()

    # -- introspection ----------------------------------------------------------------------

    def introspect(self) -> SchemaSnapshot:
        try:
            insp = inspect(self._engine)
            schema = insp.default_schema_name if self.kind == "postgresql" else None
            row_counts = self._row_counts(schema)
            tables: list[TableInfo] = []
            relationships: list[Relationship] = []
            with self._engine.connect() as conn:
                for tname in sorted(insp.get_table_names(schema=schema)):
                    pk_cols = set(insp.get_pk_constraint(tname, schema=schema).get("constrained_columns") or [])
                    fk_map: dict[str, str] = {}
                    for fk in insp.get_foreign_keys(tname, schema=schema):
                        for src, dst in zip(fk["constrained_columns"], fk["referred_columns"], strict=False):
                            fk_map[src] = f"{fk['referred_table']}.{dst}"
                            relationships.append(Relationship(tname, src, fk["referred_table"], dst))
                    row_count = row_counts.get(tname)
                    profile = row_count is not None and row_count <= _MAX_ROWS_FOR_PROFILING
                    columns = []
                    for col in insp.get_columns(tname, schema=schema):
                        ctype = str(col["type"]).upper()
                        name = col["name"]
                        samples, value_range = None, None
                        if profile and name not in pk_cols and name not in fk_map:
                            samples, value_range = self._profile_column(conn, tname, name, ctype, schema)
                        columns.append(
                            ColumnInfo(
                                name=name,
                                type=ctype,
                                nullable=bool(col.get("nullable", True)),
                                primary_key=name in pk_cols,
                                references=fk_map.get(name),
                                sample_values=samples,
                                value_range=value_range,
                            )
                        )
                    tables.append(TableInfo(name=tname, columns=columns, row_count=row_count))
            return SchemaSnapshot(dialect=self.dialect, tables=tables, relationships=relationships)
        except SQLAlchemyError as exc:
            raise DataSourceUnavailableError(detail=type(exc).__name__) from exc

    def _row_counts(self, schema: str | None) -> dict[str, int]:
        with self._engine.connect() as conn:
            if self.kind == "postgresql":
                rows = conn.execute(
                    text(
                        "SELECT c.relname, c.reltuples::bigint FROM pg_class c "
                        "JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE n.nspname = :schema AND c.relkind IN ('r', 'p')"
                    ),
                    {"schema": schema},
                ).all()
                return {name: int(n) for name, n in rows if n is not None and n >= 0}
            counts = {}
            for tname in inspect(self._engine).get_table_names():
                counts[tname] = conn.execute(select(func.count()).select_from(table(tname))).scalar_one()
            return counts

    def _profile_column(
        self, conn: Any, tname: str, cname: str, ctype: str, schema: str | None
    ) -> tuple[list[str] | None, tuple[str, str] | None]:
        tbl = table(tname, column(cname), schema=schema)
        col = tbl.c[cname]
        if any(t in ctype for t in _TEMPORAL_TYPES):
            lo, hi = conn.execute(select(func.min(col), func.max(col)).select_from(tbl)).one()
            return None, (str(lo), str(hi)) if lo is not None else None
        if any(t in ctype for t in _TEXT_TYPES) and not _SENSITIVE.search(cname):
            stmt = (
                select(col, func.count().label("n"))
                .select_from(tbl)
                .where(col.is_not(None))
                .group_by(col)
                .order_by(text("n DESC"))
                .limit(_MAX_SAMPLE_DISTINCT + 1)
            )
            values = [str(r[0]) for r in conn.execute(stmt)]
            if 0 < len(values) <= _MAX_SAMPLE_DISTINCT:
                return values, None
        return None, None

    # -- execution --------------------------------------------------------------------------

    def execute_readonly(self, sql: str, *, max_rows: int, timeout_s: float) -> RawResult:
        """Run an already-validated SELECT inside a read-only transaction with a hard timeout."""
        started = time.perf_counter()
        try:
            with self._engine.connect() as conn:
                if self.kind == "postgresql":
                    conn.exec_driver_sql("BEGIN READ ONLY")
                    conn.exec_driver_sql(f"SET LOCAL statement_timeout = {int(timeout_s * 1000)}")
                else:
                    self._install_sqlite_deadline(conn, started + timeout_s)
                result = conn.exec_driver_sql(sql)
                columns = list(result.keys())
                fetched = result.fetchmany(max_rows + 1)
                conn.rollback()
        except DBAPIError as exc:
            if _is_timeout(exc):
                raise QueryTimeoutError(f"The query exceeded the {timeout_s:g}s time limit and was cancelled.") from exc
            if isinstance(exc, OperationalError) and exc.connection_invalidated:
                raise DataSourceUnavailableError(detail="connection lost") from exc
            raise QueryExecutionError(_clean_db_error(exc)) from exc
        except SQLAlchemyError as exc:
            raise DataSourceUnavailableError(detail=type(exc).__name__) from exc

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        truncated = len(fetched) > max_rows
        rows = [list(r) for r in fetched[:max_rows]]
        return RawResult(columns=columns, rows=rows, truncated=truncated, elapsed_ms=elapsed_ms)

    @staticmethod
    def _install_sqlite_deadline(conn: Any, deadline: float) -> None:
        raw = conn.connection.dbapi_connection
        raw.set_progress_handler(lambda: 1 if time.perf_counter() > deadline else 0, 10_000)


def _is_timeout(exc: DBAPIError) -> bool:
    orig = exc.orig
    if getattr(orig, "sqlstate", None) == "57014":  # postgres query_canceled
        return True
    return isinstance(orig, sqlite3.OperationalError) and "interrupted" in str(orig).lower()


def _clean_db_error(exc: DBAPIError) -> str:
    """First line of the driver message: useful for the user and for SQL repair, no stack/URL."""
    message = str(exc.orig).strip().splitlines()[0] if exc.orig else "Database error"
    return message[:500]
