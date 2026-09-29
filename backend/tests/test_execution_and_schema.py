import pytest

from app.core.errors import QueryExecutionError, QueryTimeoutError
from app.datasources.base import ColumnInfo, Relationship, SchemaSnapshot, TableInfo
from app.datasources.sqlalchemy_connector import SQLAlchemyConnector
from app.services import schema_service
from app.services.query_executor import QueryExecutor
from app.services.sql_validator import SQLValidator, ValidationResult


@pytest.fixture(scope="module")
def snapshot(connector: SQLAlchemyConnector) -> SchemaSnapshot:
    return connector.introspect()


def _run(
    connector: SQLAlchemyConnector, snapshot: SchemaSnapshot, sql: str, *, max_rows: int = 100, timeout: float = 5
):
    validation = SQLValidator(snapshot, max_rows=max_rows).validate(sql)
    assert validation.ok, validation.errors
    return QueryExecutor(connector, timeout_s=timeout, max_rows=max_rows).execute(validation)


# -- schema discovery ------------------------------------------------------------------------


def test_introspection_finds_tables_and_relationships(snapshot: SchemaSnapshot) -> None:
    assert {t.name for t in snapshot.tables} == {"customers", "products", "orders", "order_items", "payments"}
    rels = {(r.from_table, r.from_column, r.to_table) for r in snapshot.relationships}
    assert ("orders", "customer_id", "customers") in rels
    assert ("order_items", "product_id", "products") in rels
    orders = snapshot.table("orders")
    assert orders is not None and orders.row_count and orders.row_count > 10_000


def test_introspection_collects_value_hints_but_not_personal_data(snapshot: SchemaSnapshot) -> None:
    customers = snapshot.table("customers")
    assert customers is not None
    cols = {c.name: c for c in customers.columns}
    assert set(cols["segment"].sample_values or []) == {"Consumer", "Small Business", "Corporate"}
    assert cols["email"].sample_values is None
    assert cols["first_name"].sample_values is None
    assert cols["signup_date"].value_range is not None


def test_render_schema_and_latest_date(snapshot: SchemaSnapshot) -> None:
    text = schema_service.render_schema(snapshot.tables)
    assert "Table orders" in text
    assert "customer_id INTEGER  -- references customers.customer_id" in text
    assert "'delivered'" in text
    assert schema_service.latest_data_date(snapshot.tables) == "2025-12-31"


def test_select_tables_keeps_small_schemas_whole(snapshot: SchemaSnapshot) -> None:
    assert len(schema_service.select_tables(snapshot, "revenue by city", budget=12)) == len(snapshot.tables)


def test_select_tables_picks_relevant_tables_and_join_path() -> None:
    names = ["customers", "orders", "order_items", "products", *[f"audit_{i}" for i in range(10)]]
    tables = [TableInfo(n, [ColumnInfo("id", "INTEGER", primary_key=True)]) for n in names]
    tables[0] = TableInfo("customers", [ColumnInfo("customer_id", "INTEGER"), ColumnInfo("city", "TEXT")])
    tables[3] = TableInfo("products", [ColumnInfo("product_id", "INTEGER"), ColumnInfo("category", "TEXT")])
    rels = [
        Relationship("orders", "customer_id", "customers", "customer_id"),
        Relationship("order_items", "order_id", "orders", "order_id"),
        Relationship("order_items", "product_id", "products", "product_id"),
    ]
    snap = SchemaSnapshot(dialect="sqlite", tables=tables, relationships=rels)
    chosen = {t.name for t in schema_service.select_tables(snap, "which city buys the most of each category", budget=6)}
    assert {"customers", "products"} <= chosen
    assert {"orders", "order_items"} <= chosen  # join path added
    assert not any(n.startswith("audit") for n in chosen)


# -- execution -------------------------------------------------------------------------------


def test_execute_returns_json_safe_values(connector: SQLAlchemyConnector, snapshot: SchemaSnapshot) -> None:
    data = _run(connector, snapshot, "SELECT order_id, order_date, status FROM orders ORDER BY order_id LIMIT 3")
    assert data.row_count == 3
    assert [c.name for c in data.columns] == ["order_id", "order_date", "status"]
    assert isinstance(data.rows[0][1], str) and data.rows[0][1].startswith("2024-")
    kinds = {c.name: c.kind for c in data.columns}
    assert kinds == {"order_id": "identifier", "order_date": "temporal", "status": "categorical"}


def test_execute_decimal_aggregates(connector: SQLAlchemyConnector, snapshot: SchemaSnapshot) -> None:
    data = _run(connector, snapshot, "SELECT ROUND(SUM(line_total), 2) AS total_revenue FROM order_items")
    assert isinstance(data.rows[0][0], (int, float))
    assert data.columns[0].format == "currency"


def test_truncation_is_flagged(connector: SQLAlchemyConnector, snapshot: SchemaSnapshot) -> None:
    data = _run(connector, snapshot, "SELECT order_id FROM orders", max_rows=50)
    assert data.row_count == 50
    assert data.truncated


def test_empty_result(connector: SQLAlchemyConnector, snapshot: SchemaSnapshot) -> None:
    data = _run(connector, snapshot, "SELECT * FROM orders WHERE order_date > '2030-01-01'")
    assert data.row_count == 0
    assert data.rows == []


def test_timeout_cancels_long_queries(connector: SQLAlchemyConnector, snapshot: SchemaSnapshot) -> None:
    sql = "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r) SELECT COUNT(*) AS n FROM r"
    with pytest.raises(QueryTimeoutError):
        _run(connector, snapshot, sql, timeout=0.3)


def test_executor_refuses_unvalidated_sql(connector: SQLAlchemyConnector) -> None:
    executor = QueryExecutor(connector, timeout_s=5, max_rows=10)
    with pytest.raises(ValueError):
        executor.execute(ValidationResult(ok=False, validated_sql="DELETE FROM orders"))


def test_connection_is_read_only_even_without_validation(connector: SQLAlchemyConnector) -> None:
    """Defence in depth: the driver-level connection rejects writes on its own."""
    with pytest.raises(QueryExecutionError):
        connector.execute_readonly("DELETE FROM orders", max_rows=1, timeout_s=5)
    assert connector.execute_readonly("SELECT COUNT(*) FROM orders", max_rows=1, timeout_s=5).rows[0][0] > 0


def test_database_errors_are_clean_messages(connector: SQLAlchemyConnector) -> None:
    with pytest.raises(QueryExecutionError) as exc:
        connector.execute_readonly("SELECT nope FROM orders", max_rows=1, timeout_s=5)
    assert "nope" in exc.value.message
    assert "Traceback" not in exc.value.message
