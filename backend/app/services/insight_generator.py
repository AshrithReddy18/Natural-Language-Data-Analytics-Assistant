"""Grounded insights and KPIs.

1. `compute_facts` derives statements *deterministically* from the returned rows (top item,
   share of total, period-over-period change, peak, trend...). These are always correct.
2. The LLM may rephrase those facts into a concise narrative, but only from the facts and rows.
3. `numbers_are_grounded` rejects any narrative containing a number that cannot be traced back to
   the facts or the data; in that case (or if no LLM is available) the facts are used directly.
"""

import json
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.errors import AppError
from app.core.logging import log_event
from app.llm.base import ChatTurn, LLMProvider
from app.schemas.analysis import ChartSpec, ColumnMeta, Insight, Kpi, QueryResultData
from app.schemas.llm_outputs import InsightText

logger = logging.getLogger(__name__)

CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}
_NON_ADDITIVE = re.compile(r"(avg|average|mean|median|rate|ratio|pct|percent|share|per_|aov|min_|max_|^min|^max)", re.I)

INSIGHT_SYSTEM = """You write the "Key insight" for a data analysis result.

Strict rules:
- Use ONLY the facts and rows provided. Every number you write must appear in them
  (you may round it or write it compactly, e.g. 2,412,300 as 2.41M). Never compute new numbers.
- Do not speculate about causes, forecasts, or anything not shown by the data.
- If the result is too small to support a conclusion, say so plainly.
- Headline: one sentence, at most 25 words, the single most important finding.
- Bullets: up to 3 short observations that add something the headline does not.
- Use the currency symbol given. Plain business language, no hype."""


@dataclass
class Facts:
    statements: list[str] = field(default_factory=list)
    kpis: list[Kpi] = field(default_factory=list)


def humanize(name: str) -> str:
    return name.replace("_", " ").strip()


def format_value(value: Any, fmt: str, currency: str = "INR") -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return str(value)
    if fmt == "currency":
        return CURRENCY_SYMBOLS.get(currency, currency + " ") + _compact(value)
    if fmt == "percent":
        return f"{value:.1f}%"
    if fmt == "integer" or (float(value).is_integer() and abs(value) < 1e6):
        return f"{round(value):,}"
    return _compact(value) if abs(value) >= 1e6 else f"{value:,.2f}"


def _compact(value: float) -> str:
    sign = "-" if value < 0 else ""
    v = abs(value)
    for threshold, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if v >= threshold:
            return f"{sign}{v / threshold:.2f}".rstrip("0").rstrip(".") + suffix
    return f"{sign}{v:,.2f}".rstrip("0").rstrip(".")


def _pct_change(old: float, new: float) -> float | None:
    if old == 0:
        return None
    return (new - old) / abs(old) * 100


def _col(result: QueryResultData, name: str | None) -> ColumnMeta | None:
    return next((c for c in result.columns if c.name == name), None)


def _column_values(result: QueryResultData, col: ColumnMeta) -> list[Any]:
    idx = result.columns.index(col)
    return [row[idx] for row in result.rows]


def compute_facts(result: QueryResultData, chart: ChartSpec, currency: str = "INR") -> Facts:
    if result.row_count == 0:
        return Facts(["No rows matched the question's criteria."])

    if chart.type == "kpi":
        facts = Facts()
        row = result.rows[0]
        for col in result.columns:
            if col.kind == "numeric":
                value = row[result.columns.index(col)]
                facts.statements.append(
                    f"{humanize(col.name).capitalize()} is {format_value(value, col.format, currency)}."
                )
                facts.kpis.append(Kpi(label=humanize(col.name), value=value, format=col.format))
        return facts

    x, measure = _col(result, chart.x), _col(result, chart.y[0] if chart.y else None)
    if x is None or measure is None:
        return Facts([f"The query returned {result.row_count:,} rows."])

    if chart.type == "scatter":
        return _scatter_facts(result, x, measure)
    if chart.series:
        series = _col(result, chart.series)
        if series is not None:
            return _series_facts(result, x, series, measure, currency)
    if x.kind == "temporal":
        return _time_facts(result, x, measure, currency)
    return _category_facts(result, x, measure, currency)


def _pairs(result: QueryResultData, x: ColumnMeta, m: ColumnMeta) -> list[tuple[Any, float]]:
    xi, mi = result.columns.index(x), result.columns.index(m)
    return [(r[xi], float(r[mi])) for r in result.rows if isinstance(r[mi], (int, float))]


def _category_facts(result: QueryResultData, x: ColumnMeta, m: ColumnMeta, cur: str) -> Facts:
    pairs = _pairs(result, x, m)
    if not pairs:
        return Facts([f"The query returned {result.row_count:,} rows."])
    f = Facts()
    mname, xname = humanize(m.name), humanize(x.name)
    ranked = sorted(pairs, key=lambda p: p[1], reverse=True)
    (top_label, top), n = ranked[0], len(ranked)
    fv = lambda v: format_value(v, m.format, cur)  # noqa: E731
    f.statements.append(f"{top_label} has the highest {mname}: {fv(top)}.")
    additive = not _NON_ADDITIVE.search(m.name) and m.format != "percent"
    if additive and all(v >= 0 for _, v in ranked) and n > 1:
        total = sum(v for _, v in ranked)
        # The query may have been limited (e.g. "top 10"), so never claim this is every value.
        scope = f"the {n} {xname} values returned"
        if total > 0:
            f.statements.append(
                f"{top_label} accounts for {top / total * 100:.1f}% of the combined {mname} of {scope} ({fv(total)})."
            )
            if n >= 6:
                top3 = sum(v for _, v in ranked[:3]) / total * 100
                f.statements.append(f"The top 3 together account for {top3:.1f}% of it.")
        f.kpis.append(Kpi(label=f"Total {mname}", value=total, format=m.format))
    if n > 1:
        second_label, second = ranked[1]
        if m.format == "percent":
            f.statements.append(
                f"{top_label} leads second-placed {second_label} ({fv(second)}) by {top - second:.1f} percentage points."
            )
        elif (gap := _pct_change(second, top)) is not None:
            f.statements.append(f"{top_label} is {gap:.1f}% above second-placed {second_label} ({fv(second)}).")
        low_label, low = ranked[-1]
        f.statements.append(f"The lowest is {low_label} at {fv(low)}.")
    f.kpis.append(Kpi(label=f"Top {xname}", value=str(top_label), format="text", delta_label=fv(top)))
    if m.format not in ("currency",) and not additive:
        avg = sum(v for _, v in ranked) / n
        f.statements.append(f"The average across {n} {xname} values is {fv(avg)}.")
    return f


def _time_facts(result: QueryResultData, x: ColumnMeta, m: ColumnMeta, cur: str) -> Facts:
    pairs = sorted(_pairs(result, x, m), key=lambda p: str(p[0]) if not isinstance(p[0], (int, float)) else p[0])
    if not pairs:
        return Facts([f"The query returned {result.row_count:,} rows."])
    f = Facts()
    mname = humanize(m.name)
    fv = lambda v: format_value(v, m.format, cur)  # noqa: E731
    (first_x, first), (last_x, last) = pairs[0], pairs[-1]
    peak_x, peak = max(pairs, key=lambda p: p[1])
    low_x, low = min(pairs, key=lambda p: p[1])
    additive = not _NON_ADDITIVE.search(m.name) and m.format != "percent"
    n = len(pairs)

    f.statements.append(f"{mname.capitalize()} peaked in {peak_x} at {fv(peak)}; the lowest was {low_x} at {fv(low)}.")
    change = _pct_change(first, last)
    if change is not None and n > 1:
        direction = "rose" if change > 0 else "fell"
        f.statements.append(
            f"From {first_x} to {last_x}, {mname} {direction} {abs(change):.1f}% ({fv(first)} → {fv(last)})."
        )
    if n >= 3:
        prev_x, prev = pairs[-2]
        recent = _pct_change(prev, last)
        if recent is not None:
            f.statements.append(
                f"The latest period ({last_x}) was {abs(recent):.1f}% {'above' if recent >= 0 else 'below'} the one before ({prev_x})."
            )
    if n >= 4:
        slope = _slope([v for _, v in pairs])
        mean = sum(v for _, v in pairs) / n
        rel = slope * (n - 1) / mean * 100 if mean else 0
        trend = "upward" if rel > 5 else "downward" if rel < -5 else "broadly flat"
        f.statements.append(f"Across {n} periods the overall trend is {trend}.")
    if additive:
        total = sum(v for _, v in pairs)
        f.statements.append(f"Total {mname} over the period: {fv(total)}; average per period {fv(total / n)}.")
        f.kpis.append(Kpi(label=f"Total {mname}", value=total, format=m.format))
        if peak > 0 and total > 0 and n >= 4:
            f.statements.append(f"The peak period {peak_x} contributed {peak / total * 100:.1f}% of the total.")
    if change is not None and n > 1:
        f.kpis.append(
            Kpi(
                label=f"Change {first_x} → {last_x}",
                value=last,
                format=m.format,
                delta_pct=round(change, 1),
                delta_label=f"vs {fv(first)}",
            )
        )
    f.kpis.append(Kpi(label="Peak period", value=str(peak_x), format="text", delta_label=fv(peak)))
    return f


def _series_facts(result: QueryResultData, x: ColumnMeta, s: ColumnMeta, m: ColumnMeta, cur: str) -> Facts:
    xi, si, mi = (result.columns.index(c) for c in (x, s, m))
    totals: dict[Any, float] = {}
    peaks: dict[Any, tuple[Any, float]] = {}
    for row in result.rows:
        if not isinstance(row[mi], (int, float)):
            continue
        key, value = row[si], float(row[mi])
        totals[key] = totals.get(key, 0.0) + value
        if key not in peaks or value > peaks[key][1]:
            peaks[key] = (row[xi], value)
    f = Facts()
    mname = humanize(m.name)
    fv = lambda v: format_value(v, m.format, cur)  # noqa: E731
    additive = not _NON_ADDITIVE.search(m.name) and m.format != "percent"
    keys = sorted(totals, key=lambda k: str(k))
    if additive:
        for key in keys:
            f.statements.append(f"{humanize(s.name).capitalize()} {key}: total {mname} {fv(totals[key])}.")
            f.kpis.append(Kpi(label=f"{mname.capitalize()} · {key}", value=totals[key], format=m.format))
        if len(keys) == 2:
            change = _pct_change(totals[keys[0]], totals[keys[1]])
            if change is not None:
                # The comparison is the point of a two-series question, so it leads.
                f.statements.insert(
                    0,
                    f"{keys[1]} was {abs(change):.1f}% {'higher' if change >= 0 else 'lower'} than {keys[0]} in total {mname} ({fv(totals[keys[1]])} vs {fv(totals[keys[0]])}).",
                )
                f.kpis[-1].delta_pct = round(change, 1)
                f.kpis[-1].delta_label = f"vs {keys[0]}"
    for key in keys:
        px, pv = peaks[key]
        f.statements.append(f"For {key}, the highest {humanize(x.name)} was {px} ({fv(pv)}).")
    return f


def _scatter_facts(result: QueryResultData, a: ColumnMeta, b: ColumnMeta) -> Facts:
    ai, bi = result.columns.index(a), result.columns.index(b)
    pts = [
        (float(r[ai]), float(r[bi]))
        for r in result.rows
        if isinstance(r[ai], (int, float)) and isinstance(r[bi], (int, float))
    ]
    if len(pts) < 3:
        return Facts([f"Only {len(pts)} data points were returned."])
    r = _pearson(pts)
    strength = "strong" if abs(r) >= 0.7 else "moderate" if abs(r) >= 0.4 else "weak"
    sign = "positive" if r >= 0 else "negative"
    return Facts(
        [
            f"{humanize(a.name).capitalize()} and {humanize(b.name)} show a {strength} {sign} correlation (r = {r:.2f}) across {len(pts)} points."
        ]
    )


def _slope(ys: list[float]) -> float:
    n = len(ys)
    mx = (n - 1) / 2
    my = sum(ys) / n
    num = sum((i - mx) * (y - my) for i, y in enumerate(ys))
    den = sum((i - mx) ** 2 for i in range(n))
    return num / den if den else 0.0


def _pearson(pts: list[tuple[float, float]]) -> float:
    n = len(pts)
    mx, my = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    sxy = sum((x - mx) * (y - my) for x, y in pts)
    sxx = math.sqrt(sum((x - mx) ** 2 for x, _ in pts))
    syy = math.sqrt(sum((y - my) ** 2 for _, y in pts))
    return sxy / (sxx * syy) if sxx and syy else 0.0


# -- grounding check -----------------------------------------------------------------------

_NUMBER_RE = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?(?:\s?(?:%|[kKmMbB]\b|L\b|Cr\b|lakh|crore))?")
_SUFFIX = {"k": 1e3, "m": 1e6, "b": 1e9, "l": 1e5, "lakh": 1e5, "cr": 1e7, "crore": 1e7}


def _parse_numbers(text: str) -> list[float]:
    values = []
    for token in _NUMBER_RE.findall(text):
        t = token.replace(",", "").strip()
        m = re.match(r"([-+]?\d+(?:\.\d+)?)\s?(%|[a-zA-Z]+)?$", t)
        if not m:
            continue
        value = float(m.group(1))
        suffix = (m.group(2) or "").lower()
        values.append(value * _SUFFIX.get(suffix, 1))
    return values


def numbers_are_grounded(text: str, facts: list[str], rows: list[list[Any]]) -> bool:
    allowed: list[float] = []
    for fact in facts:
        allowed.extend(_parse_numbers(fact))
    for row in rows:
        for v in row:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                allowed.append(float(v))
            elif isinstance(v, str):
                allowed.extend(_parse_numbers(v))
    for value in _parse_numbers(text):
        if abs(value) <= 12 or (1900 <= value <= 2100 and value.is_integer()):
            continue  # small counts ("top 3") and years
        if not any(_close(value, a) for a in allowed):
            return False
    return True


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= 0.051 * max(1.0, abs(b) / 100) or (b != 0 and abs(a - b) / abs(b) < 0.015)


# -- generation ----------------------------------------------------------------------------


class InsightGenerator:
    def __init__(self, provider: LLMProvider | None) -> None:
        self.provider = provider

    def generate(
        self,
        *,
        question: str,
        interpretation: str | None,
        result: QueryResultData,
        facts: Facts,
        currency: str,
    ) -> Insight:
        rules = Insight(
            headline=facts.statements[0], bullets=facts.statements[1:4], facts=facts.statements, generated_by="rules"
        )
        if self.provider is None or result.row_count == 0 or len(facts.statements) < 2:
            return rules
        sample = result.rows[:30]
        payload = {
            "question": question,
            "interpretation": interpretation,
            "currency_symbol": CURRENCY_SYMBOLS.get(currency, currency),
            "columns": [f"{c.name} ({c.format})" for c in result.columns],
            "facts": facts.statements,
            "rows": sample,
            "rows_shown": f"{len(sample)} of {result.row_count}",
        }
        try:
            text = self.provider.generate_structured(
                system=INSIGHT_SYSTEM,
                messages=[ChatTurn("user", json.dumps(payload, default=str))],
                output_type=InsightText,
                effort="low",
                max_tokens=2000,
            )
        except AppError as exc:
            log_event(logger, "insight_llm_failed", logging.WARNING, code=exc.code)
            return rules
        narrative = " ".join([text.headline, *text.bullets])
        if not numbers_are_grounded(narrative, facts.statements, result.rows):
            log_event(logger, "insight_ungrounded_rejected", logging.WARNING)
            return rules
        return Insight(headline=text.headline, bullets=text.bullets[:3], facts=facts.statements, generated_by="llm")
