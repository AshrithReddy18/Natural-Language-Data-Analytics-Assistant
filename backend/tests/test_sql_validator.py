import pytest

from app.datasources.base import ColumnInfo, SchemaSnapshot, TableInfo
from app.services.sql_validator import SQLValidator


def _schema(dialect: str) -> SchemaSnapshot:
    return SchemaSnapshot(
        dialect=dialect,
        tables=[
            TableInfo(
                "customers",
                [ColumnInfo("customer_id", "INTEGER", primary_key=True), ColumnInfo("city", "VARCHAR")],
            ),
            TableInfo(
                "orders",
                [
                    ColumnInfo("order_id", "INTEGER", primary_key=True),
                    ColumnInfo("customer_id", "INTEGER", references="customers.customer_id"),
                    ColumnInfo("order_date", "DATE"),
                    ColumnInfo("status", "VARCHAR"),
                    ColumnInfo("revenue", "NUMERIC"),
                ],
            ),
        ],
    )


@pytest.fixture(params=["postgres", "sqlite"])
def validator(request: pytest.FixtureRequest) -> SQLValidator:
    return SQLValidator(_schema(request.param), max_rows=500)


@pytest.fixture
def pg() -> SQLValidator:
    return SQLValidator(_schema("postgres"), max_rows=500)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO orders (order_id) VALUES (1)",
        "UPDATE orders SET revenue = 0",
        "DELETE FROM orders",
        "DROP TABLE orders",
        "ALTER TABLE orders ADD COLUMN x INT",
        "TRUNCATE orders",
        "CREATE TABLE x (id INT)",
        "CREATE VIEW v AS SELECT * FROM orders",
        "GRANT ALL ON orders TO public",
        "SELECT 1; DROP TABLE orders",
        "SELECT * FROM orders; DELETE FROM orders",
        "SELECT * INTO backup FROM orders",
        "BEGIN",
    ],
)
def test_rejects_destructive_and_non_select(validator: SQLValidator, sql: str) -> None:
    result = validator.validate(sql)
    assert not result.ok
    assert result.validated_sql is None
    assert result.errors


def test_rejects_writable_cte(pg: SQLValidator) -> None:
    result = pg.validate("WITH d AS (DELETE FROM orders RETURNING *) SELECT * FROM d")
    assert not result.ok
    assert "DELETE" in result.error_message


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT pg_sleep(10)",
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT set_config('statement_timeout', '0', false)",
        "SELECT nextval('orders_order_id_seq')",
        "SELECT * FROM dblink('host=x', 'select 1') AS t(a int)",
        "COPY orders TO '/tmp/out.csv'",
    ],
)
def test_rejects_dangerous_postgres_functions(pg: SQLValidator, sql: str) -> None:
    assert not pg.validate(sql).ok


@pytest.mark.parametrize(
    "sql",
    ["SELECT * FROM pg_catalog.pg_user", "SELECT * FROM information_schema.tables", "SELECT * FROM pg_shadow"],
)
def test_rejects_system_catalogs(pg: SQLValidator, sql: str) -> None:
    assert not pg.validate(sql).ok


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT city, COUNT(*) AS n FROM customers GROUP BY city ORDER BY n DESC LIMIT 5",
        "SELECT c.city, SUM(o.revenue) AS total FROM orders o JOIN customers c ON c.customer_id = o.customer_id GROUP BY c.city",
        "WITH t AS (SELECT customer_id, SUM(revenue) AS r FROM orders GROUP BY customer_id) SELECT AVG(r) AS avg_r FROM t",
        "SELECT order_id, revenue, RANK() OVER (ORDER BY revenue DESC) AS rnk FROM orders",
        "SELECT city FROM customers UNION SELECT status FROM orders",
        "SELECT * FROM orders WHERE customer_id IN (SELECT customer_id FROM customers WHERE city = 'Pune')",
        "SELECT 'DROP TABLE orders; --' AS harmless FROM orders LIMIT 1",
    ],
)
def test_accepts_read_only_queries(validator: SQLValidator, sql: str) -> None:
    result = validator.validate(sql)
    assert result.ok, result.errors
    assert result.validated_sql


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT date_trunc('month', order_date) AS month, SUM(revenue) FROM orders GROUP BY 1",
        "SELECT EXTRACT(YEAR FROM order_date) AS yr, ROUND(SUM(revenue)::numeric, 2) FROM orders GROUP BY 1",
        "SELECT * FROM customers WHERE city ILIKE 'hyd%'",
        "SELECT * FROM orders WHERE order_date >= CURRENT_DATE - INTERVAL '30 days'",
        "SELECT d::date AS day FROM generate_series('2025-01-01'::date, '2025-01-31'::date, '1 day') AS d",
    ],
)
def test_accepts_postgres_idioms(pg: SQLValidator, sql: str) -> None:
    result = pg.validate(sql)
    assert result.ok, result.errors


def test_unknown_table_lists_available_tables(validator: SQLValidator) -> None:
    result = validator.validate("SELECT * FROM sales")
    assert not result.ok
    assert "`sales` does not exist" in result.error_message
    assert "customers" in result.error_message


def test_unknown_column_is_reported(validator: SQLValidator) -> None:
    result = validator.validate("SELECT city, SUM(sales_amount) FROM customers GROUP BY city")
    assert not result.ok
    assert "sales_amount" in result.error_message


def test_ambiguous_or_wrong_table_column_is_reported(validator: SQLValidator) -> None:
    result = validator.validate("SELECT c.revenue FROM customers c")
    assert not result.ok


def test_limit_added_when_missing(validator: SQLValidator) -> None:
    result = validator.validate("SELECT * FROM orders")
    assert result.ok
    assert result.limit_applied == 500
    assert "LIMIT 500" in (result.validated_sql or "")


def test_limit_clamped_when_too_large(validator: SQLValidator) -> None:
    result = validator.validate("SELECT * FROM orders LIMIT 100000")
    assert result.ok
    assert result.limit_applied == 500
    assert result.warnings


def test_small_limit_kept(validator: SQLValidator) -> None:
    result = validator.validate("SELECT * FROM orders LIMIT 10")
    assert result.ok
    assert result.limit_applied is None
    assert "LIMIT 10" in (result.validated_sql or "")


def test_empty_and_unparseable(validator: SQLValidator) -> None:
    assert not validator.validate("   ").ok
    assert not validator.validate("SELEC city FRM customers").ok


def test_trailing_semicolon_is_fine(validator: SQLValidator) -> None:
    assert validator.validate("SELECT city FROM customers;").ok


def test_tables_are_reported(validator: SQLValidator) -> None:
    result = validator.validate(
        "SELECT c.city FROM orders o JOIN customers c ON c.customer_id = o.customer_id",
    )
    assert sorted(result.tables) == ["customers", "orders"]


def test_column_error_says_which_table_has_the_column(validator: SQLValidator) -> None:
    result = validator.validate("SELECT c.order_date FROM customers c")
    assert not result.ok
    assert "is a column of: orders" in result.error_message


def test_column_error_for_nonexistent_column(validator: SQLValidator) -> None:
    result = validator.validate("SELECT sales_amount FROM orders")
    assert "No table has a column named `sales_amount`" in result.error_message


def test_column_error_explains_aliased_table(validator: SQLValidator) -> None:
    result = validator.validate("SELECT orders.order_date FROM orders AS o")
    assert not result.ok
    assert "is aliased in this query" in result.error_message
