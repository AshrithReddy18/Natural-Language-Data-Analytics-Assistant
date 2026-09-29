"""AST-based validation of model-generated SQL.

Nothing reaches a database unless it passes every check here. Validation is done on the parsed
syntax tree (sqlglot), not with regular expressions, so tricks like comments, string literals
containing keywords, or stacked statements cannot smuggle a write through.

Defence in depth: even validated SQL is executed in a read-only transaction (PostgreSQL) or on a
read-only connection (SQLite) with a statement timeout; see `SQLAlchemyConnector`.
"""

from dataclasses import dataclass, field
from typing import cast

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, ParseError, SqlglotError
from sqlglot.optimizer.qualify import qualify

from app.datasources.base import SchemaSnapshot

MAX_SQL_LENGTH = 20_000


def _node_types(*names: str) -> tuple[type[exp.Expression], ...]:
    """Resolve expression classes by name, tolerating sqlglot versions that lack some of them."""
    return tuple(t for n in names if isinstance(t := getattr(exp, n, None), type))


ALLOWED_ROOTS = _node_types("Select", "Union", "Intersect", "Except", "SetOperation", "Subquery")

# Any of these anywhere in the tree rejects the query.
FORBIDDEN_NODES = _node_types(
    "Insert",
    "Update",
    "Delete",
    "Merge",
    "Drop",
    "Create",
    "Alter",
    "AlterTable",
    "TruncateTable",
    "Command",
    "Copy",
    "Grant",
    "Revoke",
    "Transaction",
    "Commit",
    "Rollback",
    "Set",
    "Pragma",
    "Use",
    "LoadData",
    "Into",
    "Lock",
    "Analyze",
    "Attach",
    "Detach",
)

# Functions that read the server filesystem, sleep, reach other servers, change settings or
# sequences, or otherwise have side effects.
FORBIDDEN_FUNCTIONS = {
    "pg_sleep",
    "pg_sleep_for",
    "pg_sleep_until",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    "pg_logdir_ls",
    "lo_import",
    "lo_export",
    "lo_get",
    "lo_put",
    "lo_unlink",
    "lo_create",
    "dblink",
    "dblink_exec",
    "dblink_connect",
    "pg_terminate_backend",
    "pg_cancel_backend",
    "pg_reload_conf",
    "pg_rotate_logfile",
    "set_config",
    "current_setting",
    "nextval",
    "setval",
    "pg_advisory_lock",
    "pg_advisory_xact_lock",
    "pg_try_advisory_lock",
    "query_to_xml",
    "table_to_xml",
    "cursor_to_xml",
    "database_to_xml",
    "pg_switch_wal",
    "load_extension",
    "readfile",
    "writefile",
    "fts3_tokenizer",
    "edit",
    "zeroblob",
    "sqlite_compileoption_get",
    "version",
    "inet_server_addr",
}


@dataclass
class ValidationResult:
    ok: bool
    validated_sql: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    limit_applied: int | None = None

    @property
    def error_message(self) -> str:
        return " ".join(self.errors)


class SQLValidator:
    def __init__(self, schema: SchemaSnapshot, *, max_rows: int) -> None:
        self.schema = schema
        self.dialect = schema.dialect
        self.max_rows = max_rows

    def validate(self, sql: str) -> ValidationResult:
        sql = (sql or "").strip().rstrip(";").strip()
        if not sql:
            return ValidationResult(ok=False, errors=["The query is empty."])
        if len(sql) > MAX_SQL_LENGTH:
            return ValidationResult(ok=False, errors=["The query is too long."])

        # 1. Parse: exactly one statement, and it must be a query.
        try:
            statements = [s for s in sqlglot.parse(sql, read=self.dialect) if s is not None]
        except (ParseError, SqlglotError) as exc:
            return ValidationResult(ok=False, errors=[f"Could not parse the SQL: {_first_line(exc)}"])
        if len(statements) != 1:
            return ValidationResult(ok=False, errors=["Only a single SQL statement is allowed; found several."])
        root = statements[0]
        if not isinstance(root, ALLOWED_ROOTS):
            kind = root.key.upper()
            return ValidationResult(ok=False, errors=[f"Only read-only SELECT queries are allowed (got {kind})."])

        errors: list[str] = []

        # 2. No write/DDL/session nodes anywhere (including inside CTEs and subqueries).
        for node in root.walk():
            if isinstance(node, FORBIDDEN_NODES):
                errors.append(f"Statements of type {node.key.upper()} are not allowed.")
                break
            if isinstance(node, exp.Func):
                fname = _function_name(node)
                if fname in FORBIDDEN_FUNCTIONS:
                    errors.append(f"The function {fname}() is not allowed.")
                    break
        if errors:
            return ValidationResult(ok=False, errors=errors)

        # 3. Every referenced table exists in the connected schema.
        cte_names = {cte.alias_or_name.lower() for cte in root.find_all(exp.CTE)}
        tables: list[str] = []
        for tbl in root.find_all(exp.Table):
            if not isinstance(tbl.this, exp.Identifier):
                continue  # table-valued function such as generate_series(); checked above
            name = tbl.name
            if name.lower() in cte_names:
                continue
            if tbl.args.get("catalog") or (tbl.db and not self._is_default_schema(tbl.db)):
                errors.append(f"Table `{tbl.sql(dialect=self.dialect)}` is outside the connected schema.")
                continue
            known = self.schema.table(name)
            if known is None:
                errors.append(
                    f"Table `{name}` does not exist. Available tables: {', '.join(t.name for t in self.schema.tables)}."
                )
            elif known.name not in tables:
                tables.append(known.name)
        if errors:
            return ValidationResult(ok=False, errors=errors, tables=tables)

        # 4. Every referenced column resolves against those tables.
        column_error = self._check_columns(root)
        if column_error:
            return ValidationResult(ok=False, errors=[column_error], tables=tables)

        # 5. Enforce a row limit.
        warnings: list[str] = []
        limit_applied = None
        current = _literal_limit(root)
        if current is None or current > self.max_rows:
            root = root.limit(self.max_rows, copy=False) if hasattr(root, "limit") else root
            limit_applied = self.max_rows
            if current is not None:
                warnings.append(f"LIMIT {current} reduced to the maximum of {self.max_rows} rows.")

        validated = root.sql(dialect=self.dialect, pretty=True)
        return ValidationResult(
            ok=True,
            validated_sql=validated,
            warnings=warnings,
            tables=tables,
            limit_applied=limit_applied,
        )

    def _is_default_schema(self, db: str) -> bool:
        return db.lower() in {"public", "main"}

    def _check_columns(self, root: exp.Expression) -> str | None:
        try:
            qualify(
                root.copy(),
                schema=cast(dict[str, object], self.schema.as_sqlglot_schema()),
                dialect=self.dialect,
                validate_qualify_columns=True,
                identify=False,
            )
        except OptimizeError as exc:
            message = _first_line(exc)
            # Rephrase sqlglot's wording into something the user and the model can act on.
            if "could not be resolved" in message.lower():
                return message.split(". Line:")[0] + (" — it does not exist in the referenced tables.")
            return f"Column check failed: {message}"
        except SqlglotError:
            # Constructs the qualifier does not understand are not a safety issue (tables and
            # forbidden operations are already checked); let the database be the judge.
            return None
        return None


def _function_name(node: exp.Func) -> str:
    if isinstance(node, exp.Anonymous):
        return str(node.this).lower()
    return node.sql_name().lower()


def _literal_limit(root: exp.Expression) -> int | None:
    limit = root.args.get("limit")
    if limit is None:
        return None
    value = limit.expression if isinstance(limit, exp.Limit) else limit
    if isinstance(value, exp.Literal) and value.is_int:
        return int(value.this)
    return 10**9  # non-literal limit (e.g. an expression): treat as unbounded and replace


def _first_line(exc: Exception) -> str:
    text = str(exc).strip()
    return text.splitlines()[0][:300] if text else type(exc).__name__
