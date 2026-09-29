from typing import Any

import pytest

from app.schemas.analysis import QueryResultData
from app.schemas.llm_outputs import InsightText
from app.services.chart_recommender import recommend_chart
from app.services.insight_generator import InsightGenerator, compute_facts, format_value, numbers_are_grounded
from app.services.result_analyzer import profile_columns
from tests.fakes import FakeProvider


def result(columns: list[str], rows: list[list[Any]]) -> QueryResultData:
    return QueryResultData(columns=profile_columns(columns, rows), rows=rows, row_count=len(rows), execution_ms=1)


MONTHLY = result(
    ["month", "total_revenue"],
    [["2025-01", 820_000.0], ["2025-02", 910_000.0], ["2025-03", 950_000.0], ["2025-04", 1_200_000.0]],
)
CITIES = result(
    ["city", "revenue"],
    [["Hyderabad", 2_400_000.0], ["Bengaluru", 2_100_000.0], ["Mumbai", 1_900_000.0], ["Delhi", 1_700_000.0]],
)


# -- profiling -------------------------------------------------------------------------------


def test_profile_kinds_and_formats() -> None:
    r = result(
        ["order_date", "year", "customer_id", "segment", "revenue", "order_count", "repeat_pct"],
        [["2025-01-03", 2025, 17, "Consumer", 1234.5, 3, 33.4], ["2025-01-04", 2025, 18, "Corporate", 99.0, 1, 12.0]],
    )
    meta = {c.name: (c.kind, c.format) for c in r.columns}
    assert meta["order_date"] == ("temporal", "date")
    assert meta["year"] == ("temporal", "integer")
    assert meta["customer_id"][0] == "identifier"
    assert meta["segment"] == ("categorical", "text")
    assert meta["revenue"] == ("numeric", "currency")
    assert meta["order_count"] == ("numeric", "integer")
    assert meta["repeat_pct"] == ("numeric", "percent")


# -- chart recommendation --------------------------------------------------------------------


def test_time_series_gets_line_chart() -> None:
    chart = recommend_chart(MONTHLY)
    assert (chart.type, chart.x, chart.y) == ("line", "month", ["total_revenue"])


def test_categories_get_bar_chart() -> None:
    assert recommend_chart(CITIES).type == "bar"


def test_many_categories_get_horizontal_bar() -> None:
    r = result(["product_name", "revenue"], [[f"Product number {i}", float(100 - i)] for i in range(15)])
    assert recommend_chart(r).type == "horizontal_bar"


def test_share_with_few_categories_gets_donut() -> None:
    r = result(["method", "share_pct"], [["UPI", 45.0], ["Card", 35.0], ["COD", 20.0]])
    assert recommend_chart(r).type == "donut"


def test_single_row_gets_kpis() -> None:
    r = result(["total_orders", "total_revenue"], [[48293, 12_400_000.0]])
    chart = recommend_chart(r)
    assert chart.type == "kpi" and chart.y == ["total_orders", "total_revenue"]


def test_year_series_comparison() -> None:
    r = result(
        ["month_num", "year", "revenue"],
        [[1, 2024, 10.0], [1, 2025, 12.0], [2, 2024, 11.0], [2, 2025, 15.0], [3, 2024, 9.0], [3, 2025, 14.0]],
    )
    chart = recommend_chart(r)
    assert (chart.type, chart.x, chart.series) == ("line", "month_num", "year")


def test_two_measures_get_scatter() -> None:
    r = result(["unit_price", "unit_cost"], [[float(i * 10), float(i * 6)] for i in range(1, 8)])
    assert recommend_chart(r).type == "scatter"


def test_no_numeric_column_is_a_table() -> None:
    r = result(["city", "state"], [["Pune", "Maharashtra"], ["Kochi", "Kerala"]])
    assert recommend_chart(r).type == "table"


# -- facts & KPIs ----------------------------------------------------------------------------


def test_category_facts_are_correct() -> None:
    facts = compute_facts(CITIES, recommend_chart(CITIES), "INR")
    joined = " ".join(facts.statements)
    assert "Hyderabad has the highest revenue: ₹2.4M" in joined
    assert "29.6%" in joined  # 2.4 / 8.1
    assert "14.3% above second-placed Bengaluru" in joined
    labels = [k.label for k in facts.kpis]
    assert "Total revenue" in labels and "Top city" in labels


def test_time_facts_are_correct() -> None:
    facts = compute_facts(MONTHLY, recommend_chart(MONTHLY), "INR")
    joined = " ".join(facts.statements)
    assert "peaked in 2025-04" in joined
    assert "rose 46.3%" in joined  # 820k -> 1.2M
    assert "upward" in joined
    change = next(k for k in facts.kpis if k.label.startswith("Change"))
    assert change.delta_pct == pytest.approx(46.3, abs=0.1)


def test_average_measures_are_not_summed() -> None:
    r = result(["segment", "avg_order_value"], [["Consumer", 5900.0], ["Corporate", 14300.0]])
    facts = compute_facts(r, recommend_chart(r), "INR")
    assert not any(k.label.startswith("Total") for k in facts.kpis)


def test_format_value() -> None:
    assert format_value(2_412_300.0, "currency", "INR") == "₹2.41M"
    assert format_value(48293, "integer") == "48,293"
    assert format_value(33.44, "percent") == "33.4%"


# -- grounding -------------------------------------------------------------------------------


def test_grounding_accepts_numbers_from_facts_and_rows() -> None:
    facts = ["Hyderabad has the highest revenue: ₹2.4M.", "It accounts for 29.6% of the combined revenue."]
    assert numbers_are_grounded("Hyderabad leads with ₹2.4M, about 29.6% of revenue.", facts, CITIES.rows)
    assert numbers_are_grounded("Mumbai recorded 1,900,000 in revenue.", facts, CITIES.rows)


def test_grounding_rejects_invented_numbers() -> None:
    facts = ["Hyderabad has the highest revenue: ₹2.4M."]
    assert not numbers_are_grounded("Revenue grew 47% year over year.", facts, CITIES.rows)
    assert not numbers_are_grounded("Hyderabad made ₹9.9M.", facts, CITIES.rows)


def test_insight_uses_llm_text_when_grounded() -> None:
    facts = compute_facts(CITIES, recommend_chart(CITIES), "INR")
    provider = FakeProvider(
        insight=InsightText(headline="Hyderabad leads revenue at ₹2.4M.", bullets=["Bengaluru follows at ₹2.1M."])
    )
    insight = InsightGenerator(provider).generate(
        question="q", interpretation=None, result=CITIES, facts=facts, currency="INR"
    )
    assert insight.generated_by == "llm"
    assert insight.headline.startswith("Hyderabad leads")


def test_insight_falls_back_when_llm_invents_numbers() -> None:
    facts = compute_facts(CITIES, recommend_chart(CITIES), "INR")
    provider = FakeProvider(insight=InsightText(headline="Revenue will grow 35% next year.", bullets=[]))
    insight = InsightGenerator(provider).generate(
        question="q", interpretation=None, result=CITIES, facts=facts, currency="INR"
    )
    assert insight.generated_by == "rules"
    assert insight.headline == facts.statements[0]


def test_insight_falls_back_when_llm_unavailable() -> None:
    facts = compute_facts(CITIES, recommend_chart(CITIES), "INR")
    insight = InsightGenerator(FakeProvider()).generate(
        question="q", interpretation=None, result=CITIES, facts=facts, currency="INR"
    )
    assert insight.generated_by == "rules"
