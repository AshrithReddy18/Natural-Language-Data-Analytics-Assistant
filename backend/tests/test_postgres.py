"""PostgreSQL integration tests. Run with a scratch database:

    TEST_POSTGRES_URL=postgresql://user:pw@localhost:5432/scratch pytest tests/test_postgres.py

Skipped when TEST_POSTGRES_URL is not set.
"""

import os
from collections.abc import Iterator

import pytest

from app.core.config import get_settings
from app.core.errors import QueryExecutionError, QueryTimeoutError
from app.datasources.base import SchemaSnapshot
from app.datasources.sqlalchemy_connector import SQLAlchemyConnector
from app.demo.seed import seed
from app.services.analysis_pipeline import AnalysisPipeline
from app.services.query_executor import QueryExecutor
from app.services.sql_validator import SQLValidator
from tests.fakes import FakeProvider, plan

PG_URL = os.environ.get("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_POSTGRES_URL not set")


@pytest.fixture(scope="module")
def pg() -> Iterator[SQLAlchemyConnector]:
    assert PG_URL
    seed(PG_URL, if_empty=True)
    connector = SQLAlchemyConnector(PG_URL)
    yield connector
    connector.dispose()


@pytest.fixture(scope="module")
def snapshot(pg: SQLAlchemyConnector) -> SchemaSnapshot:
    return pg.introspect()


def run(pg: SQLAlchemyConnector, snapshot: SchemaSnapshot, sql: str, timeout: float = 10):
    validation = SQLValidator(snapshot, max_rows=500).validate(sql)
    assert validation.ok, validation.errors
    return QueryExecutor(pg, timeout_s=timeout, max_rows=500).execute(validation)


def test_introspection(pg: SQLAlchemyConnector, snapshot: SchemaSnapshot) -> None:
    assert pg.dialect == "postgres"
    assert {t.name for t in snapshot.tables} == {"customers", "products", "orders", "order_items", "payments"}
    assert any(r.from_table == "orders" and r.to_table == "customers" for r in snapshot.relationships)
    orders = snapshot.table("orders")
    assert orders and orders.row_count and orders.row_count > 10_000
    status = next(c for c in orders.columns if c.name == "status")
    assert set(status.sample_values or []) >= {"delivered", "cancelled"}


def test_postgres_idioms_execute(pg: SQLAlchemyConnector, snapshot: SchemaSnapshot) -> None:
    data = run(
        pg,
        snapshot,
        """
        SELECT to_char(date_trunc('month', o.order_date), 'YYYY-MM') AS month,
               ROUND(SUM(oi.line_total)::numeric, 2) AS revenue,
               COUNT(DISTINCT o.order_id) AS orders
        FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
        WHERE EXTRACT(YEAR FROM o.order_date) = 2025 AND o.status ILIKE 'deliv%'
        GROUP BY 1 ORDER BY 1
        """,
    )
    assert data.row_count == 12
    assert isinstance(data.rows[0][1], float)  # Decimal normalised
    assert [c.kind for c in data.columns] == ["temporal", "numeric", "numeric"]


def test_statement_timeout(pg: SQLAlchemyConnector, snapshot: SchemaSnapshot) -> None:
    with pytest.raises(QueryTimeoutError):
        run(pg, snapshot, "SELECT COUNT(*) AS n FROM generate_series(1, 10000000000) AS g", timeout=0.5)


def test_transaction_is_read_only(pg: SQLAlchemyConnector) -> None:
    """Even SQL that bypassed validation cannot write: the transaction itself is read-only."""
    with pytest.raises(QueryExecutionError) as exc:
        pg.execute_readonly("DELETE FROM payments WHERE payment_id = 1", max_rows=1, timeout_s=5)
    assert "read-only" in exc.value.message
    with pytest.raises(QueryExecutionError):
        pg.execute_readonly("CREATE TABLE sneaky (id int)", max_rows=1, timeout_s=5)
    assert (
        pg.execute_readonly("SELECT COUNT(*) FROM payments WHERE payment_id = 1", max_rows=1, timeout_s=5).rows[0][0]
        == 1
    )


def test_pipeline_end_to_end(pg: SQLAlchemyConnector) -> None:
    sql = (
        "SELECT c.region, ROUND(SUM(oi.line_total)::numeric, 2) AS revenue FROM orders o "
        "JOIN order_items oi ON oi.order_id = o.order_id JOIN customers c ON c.customer_id = o.customer_id "
        "GROUP BY c.region ORDER BY revenue DESC"
    )
    provider = FakeProvider(plans=[plan("SELECT region, SUM(amount) FROM customers GROUP BY region"), plan(sql)])
    pipeline = AnalysisPipeline(settings=get_settings(), source_id="pg-test", connector=pg, provider=provider)
    result = pipeline.run("Revenue by region", [])
    assert result.status == "success", result.error
    assert result.sql and [a.stage for a in result.sql.attempts] == ["validation", "success"]
    assert "PostgreSQL" in provider.sql_calls[0].system
    assert result.chart and result.chart.type in ("bar", "donut")
