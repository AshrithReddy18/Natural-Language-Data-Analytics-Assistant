"""Picks a visualization from the *shape* of the result, using the model's hint as a tiebreaker.

time + metric                 → line (bar when there are only a couple of periods)
time + small category + metric→ multi-series line
category + metric             → bar; horizontal bar for long labels or many categories
part-to-whole, few categories → donut
two metrics, no dimension     → scatter
one row of metrics            → KPI cards
anything else                 → table
"""

from app.schemas.analysis import ChartSpec, ChartType, ColumnMeta, QueryResultData

MAX_BAR_CATEGORIES = 25
MAX_DONUT_SLICES = 6
MAX_SERIES = 6


def recommend_chart(
    result: QueryResultData, *, title: str = "", hint: str = "auto", measures: list[str] | None = None
) -> ChartSpec:
    cols = result.columns
    n = result.row_count
    if n == 0:
        return ChartSpec(type="table", title=title, reason="No rows to visualize.")

    numeric = [c for c in cols if c.kind == "numeric"]
    if measures:  # prefer the model's declared measures, in its order, when they are numeric
        preferred = [c for m in measures for c in numeric if c.name == m]
        numeric = preferred + [c for c in numeric if c not in preferred]
    temporal = [c for c in cols if c.kind == "temporal"]
    categorical = [c for c in cols if c.kind in ("categorical", "boolean")]

    if n == 1 and numeric and len(cols) - len(numeric) <= 1:
        return ChartSpec(
            type="kpi",
            y=[c.name for c in numeric[:4]],
            title=title,
            reason="A single row of metrics reads best as headline numbers.",
        )
    if not numeric:
        return ChartSpec(type="table", title=title, reason="The result has no numeric measure to plot.")

    measure = numeric[0]

    if temporal:
        x = temporal[0]
        # Year + month style results: a second temporal column with few values becomes the series.
        series = _series_column(cols, exclude=x, candidates=temporal[1:] + categorical)
        if series:
            return ChartSpec(
                type="line",
                x=x.name,
                y=[measure.name],
                series=series.name,
                title=title,
                reason=f"Trend of {measure.name} over {x.name}, split by {series.name}.",
            )
        if x.distinct_count <= 2:
            return ChartSpec(
                type="bar",
                x=x.name,
                y=[measure.name],
                title=title,
                reason="Only a couple of periods, so bars compare them more clearly.",
            )
        y = [c.name for c in numeric[:2] if _similar_scale(result, measure, c)]
        return ChartSpec(type="line", x=x.name, y=y, title=title, reason=f"{measure.name} over time.")

    if categorical:
        x = categorical[0]
        series = _series_column(cols, exclude=x, candidates=categorical[1:])
        if series:
            return ChartSpec(
                type="bar",
                x=x.name,
                y=[measure.name],
                series=series.name,
                title=title,
                max_points=MAX_BAR_CATEGORIES,
                reason=f"{measure.name} by {x.name}, grouped by {series.name}.",
            )
        part_to_whole = hint == "donut" or (measure.format == "percent" and "share" in measure.name)
        if part_to_whole and x.distinct_count <= MAX_DONUT_SLICES and _all_positive(result, measure):
            return ChartSpec(
                type="donut",
                x=x.name,
                y=[measure.name],
                title=title,
                reason="Share of the whole across a few categories.",
            )
        long_labels = _avg_label_length(result, x) > 12
        many = x.distinct_count > 8
        chart_type: ChartType = "horizontal_bar" if (hint == "horizontal_bar" or long_labels or many) else "bar"
        y = [c.name for c in numeric[:2] if _similar_scale(result, measure, c)]
        return ChartSpec(
            type=chart_type,
            x=x.name,
            y=y,
            title=title,
            max_points=MAX_BAR_CATEGORIES if n > MAX_BAR_CATEGORIES else None,
            reason=f"Compare {measure.name} across {x.name}.",
        )

    if len(numeric) >= 2 and n >= 5:
        return ChartSpec(
            type="scatter",
            x=numeric[0].name,
            y=[numeric[1].name],
            title=title,
            reason=f"Relationship between {numeric[0].name} and {numeric[1].name}.",
        )
    return ChartSpec(type="table", title=title, reason="No clear dimension to chart against.")


def _series_column(cols: list[ColumnMeta], *, exclude: ColumnMeta, candidates: list[ColumnMeta]) -> ColumnMeta | None:
    for c in candidates:
        if c is not exclude and 2 <= c.distinct_count <= MAX_SERIES:
            return c
    return None


def _values(result: QueryResultData, col: ColumnMeta) -> list[float]:
    idx = result.columns.index(col)
    return [float(r[idx]) for r in result.rows if isinstance(r[idx], (int, float))]


def _all_positive(result: QueryResultData, col: ColumnMeta) -> bool:
    return all(v >= 0 for v in _values(result, col))


def _similar_scale(result: QueryResultData, a: ColumnMeta, b: ColumnMeta) -> bool:
    """Two measures share an axis only if they have the same format and comparable magnitude."""
    if a is b:
        return True
    if a.format != b.format:
        return False
    va, vb = _values(result, a), _values(result, b)
    if not va or not vb:
        return False
    ma, mb = max(abs(v) for v in va) or 1, max(abs(v) for v in vb) or 1
    return max(ma, mb) / min(ma, mb) < 10


def _avg_label_length(result: QueryResultData, col: ColumnMeta) -> float:
    idx = result.columns.index(col)
    labels = [str(r[idx]) for r in result.rows]
    return sum(len(s) for s in labels) / max(1, len(labels))
