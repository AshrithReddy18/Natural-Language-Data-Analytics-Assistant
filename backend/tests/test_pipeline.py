from typing import Any

import pytest

from app.core.config import get_settings
from app.core.errors import LLMOutputError, LLMUnavailableError
from app.datasources.sqlalchemy_connector import SQLAlchemyConnector
from app.schemas.llm_outputs import InsightText
from app.services.analysis_pipeline import AnalysisPipeline
from app.services.text_to_sql import PriorTurn
from tests.fakes import FakeProvider, plan

CITY_SQL = (
    "SELECT c.city, ROUND(SUM(oi.line_total), 2) AS revenue FROM orders o "
    "JOIN order_items oi ON oi.order_id = o.order_id JOIN customers c ON c.customer_id = o.customer_id "
    "WHERE o.status IN ('delivered', 'shipped') GROUP BY c.city ORDER BY revenue DESC LIMIT 5"
)


def make(connector: SQLAlchemyConnector, provider: FakeProvider | None, events: list[dict[str, Any]] | None = None):
    return AnalysisPipeline(
        settings=get_settings(),
        source_id="test-source",
        connector=connector,
        provider=provider,
        emit=(events.append if events is not None else None),
    )


def test_happy_path(connector: SQLAlchemyConnector) -> None:
    provider = FakeProvider(
        plans=[plan(CITY_SQL, measures=["revenue"], dimensions=["city"])],
        insight=InsightText(headline="Bengaluru leads.", bullets=[]),
    )
    events: list[dict[str, Any]] = []
    result = make(connector, provider, events).run("Top 5 cities by revenue", [])

    assert result.status == "success"
    assert result.sql and result.sql.validation.ok
    assert result.sql.generated_sql == CITY_SQL
    assert result.sql.validated_sql and "LIMIT 5" in result.sql.validated_sql
    assert result.result and result.result.row_count == 5
    assert result.chart and result.chart.type == "bar"
    assert result.insight and result.insight.generated_by == "llm"
    assert [a.stage for a in result.sql.attempts] == ["success"]

    steps = [(e["step"], e["status"]) for e in events if e["type"] == "step"]
    assert steps == [
        ("understand", "running"), ("understand", "done"), ("schema", "running"), ("schema", "done"),
        ("generate", "running"), ("generate", "done"), ("validate", "running"), ("validate", "done"),
        ("execute", "running"), ("execute", "done"), ("visualize", "running"), ("visualize", "done"),
        ("insight", "running"), ("insight", "done"),
    ]  # fmt: skip


def test_schema_is_in_the_prompt(connector: SQLAlchemyConnector) -> None:
    provider = FakeProvider(plans=[plan(CITY_SQL)])
    make(connector, provider).run("Top cities", [])
    system = provider.sql_calls[0].system
    assert "Table orders" in system and "SQLite" in system and "2025-12-31" in system


def test_invalid_column_is_repaired(connector: SQLAlchemyConnector) -> None:
    bad = "SELECT city, SUM(sales_amount) AS revenue FROM customers GROUP BY city"
    provider = FakeProvider(plans=[plan(bad), plan(CITY_SQL)])
    result = make(connector, provider).run("Revenue by city", [])

    assert result.status == "success"
    assert result.sql is not None
    assert [a.stage for a in result.sql.attempts] == ["validation", "success"]
    assert "sales_amount" in (result.sql.attempts[0].error or "")
    repair_prompt = provider.sql_calls[1].messages[-1].content
    assert "sales_amount" in repair_prompt and "validation" in repair_prompt


def test_execution_error_is_repaired(connector: SQLAlchemyConnector) -> None:
    # Passes validation (qualifier can't know the function is missing) but fails in the database.
    bad = "SELECT city, no_such_function(city) AS x, COUNT(*) AS n FROM customers GROUP BY city"
    provider = FakeProvider(plans=[plan(bad), plan(CITY_SQL)])
    result = make(connector, provider).run("Revenue by city", [])
    assert result.status == "success"
    assert result.sql and [a.stage for a in result.sql.attempts] == ["execution", "success"]


def test_gives_up_after_max_repairs(connector: SQLAlchemyConnector) -> None:
    bad = "SELECT nonexistent FROM customers"
    attempts = get_settings().max_sql_repair_attempts + 1
    provider = FakeProvider(plans=[plan(bad) for _ in range(attempts)])
    result = make(connector, provider).run("?", [])
    assert result.status == "error"
    assert result.error and result.error.code == "sql_invalid"
    assert result.sql and len(result.sql.attempts) == attempts


def test_destructive_sql_from_model_is_never_executed(connector: SQLAlchemyConnector) -> None:
    provider = FakeProvider(plans=[plan("DELETE FROM orders") for _ in range(3)])
    result = make(connector, provider).run("delete everything", [])
    assert result.status == "error"
    assert connector.execute_readonly("SELECT COUNT(*) FROM orders", max_rows=1, timeout_s=5).rows[0][0] > 0


def test_clarification(connector: SQLAlchemyConnector) -> None:
    provider = FakeProvider(
        plans=[
            plan(
                None,
                status="clarify",
                clarification_question="Gross or net revenue?",
                clarification_options=["Gross", "Net"],
            )
        ]
    )
    result = make(connector, provider).run("revenue?", [])
    assert result.status == "clarification"
    assert result.clarification and result.clarification.options == ["Gross", "Net"]
    assert result.sql is None


def test_unanswerable(connector: SQLAlchemyConnector) -> None:
    provider = FakeProvider(
        plans=[plan(None, status="unanswerable", interpretation="There is no marketing spend data.")]
    )
    result = make(connector, provider).run("What was our ad spend?", [])
    assert result.status == "unanswerable"
    assert result.interpretation == "There is no marketing spend data."


def test_empty_result(connector: SQLAlchemyConnector) -> None:
    provider = FakeProvider(plans=[plan("SELECT order_id FROM orders WHERE order_date > '2030-01-01'")])
    result = make(connector, provider).run("orders in 2030", [])
    assert result.status == "empty"
    assert result.chart is None


@pytest.mark.parametrize(
    ("error", "code"),
    [(LLMOutputError(), "llm_bad_output"), (LLMUnavailableError(), "llm_unavailable")],
)
def test_llm_failures_become_error_results(connector: SQLAlchemyConnector, error: Exception, code: str) -> None:
    result = make(connector, FakeProvider(plans=[error])).run("anything", [])
    assert result.status == "error"
    assert result.error and result.error.code == code


def test_missing_sql_is_malformed_output(connector: SQLAlchemyConnector) -> None:
    result = make(connector, FakeProvider(plans=[plan(None)])).run("anything", [])
    assert result.error and result.error.code == "llm_bad_output"


def test_no_provider_configured(connector: SQLAlchemyConnector) -> None:
    result = make(connector, None).run("anything", [])
    assert result.error and result.error.code == "llm_not_configured"


def test_follow_up_context_is_sent(connector: SQLAlchemyConnector) -> None:
    provider = FakeProvider(plans=[plan(CITY_SQL)])
    history = [
        PriorTurn(
            question="Show monthly revenue for 2025",
            interpretation="Monthly revenue, 2025",
            sql="SELECT month, revenue FROM monthly",
            columns=["month", "revenue"],
            row_count=12,
            sample_rows=[["2025-01", 1.0]],
        )
    ]
    make(connector, provider).run("Which month was highest?", history)
    messages = provider.sql_calls[0].messages
    assert [m.role for m in messages] == ["user", "assistant", "user"]
    assert "SELECT month, revenue FROM monthly" in messages[1].content
    assert messages[-1].content == "Which month was highest?"
