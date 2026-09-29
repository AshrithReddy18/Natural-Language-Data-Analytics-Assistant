"""Profiles a result set: what kind of data each column holds and how to format it.

Kinds are inferred from values *and* names because SQLite (and computed columns in general)
carry no reliable type information.
"""

import re
from typing import Any

from app.schemas.analysis import ColumnKind, ColumnMeta, ValueFormat

_DATE_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?([ T]\d{2}:\d{2}(:\d{2})?)?")
_PERIOD_RE = re.compile(r"^(\d{4}[-/ ]?(Q[1-4]|W\d{1,2}|H[12]))$|^(Q[1-4])[-/ ]?\d{4}$", re.I)
_MONTH_NAMES = {
    m.lower()
    for m in [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Sept",
        "Oct",
        "Nov",
        "Dec",
    ]
}
_TEMPORAL_NAME = re.compile(r"(^|_)(date|day|week|month|quarter|year|period|yr|mon)(_|$)", re.I)
_ID_NAME = re.compile(r"(^id$|_id$|^id_)", re.I)
_CURRENCY_NAME = re.compile(
    r"(revenue|sales|amount|price|cost|spend|gmv|aov|profit|income|value|earning|payment|line_total"
    r"|^total$|total_(?!orders|count|customers|quantity|units|items))",
    re.I,
)
_PERCENT_NAME = re.compile(r"(pct|percent|share|rate|ratio|margin_pct|growth)", re.I)
_COUNT_NAME = re.compile(r"(count|number|num_|qty|quantity|units|orders|customers|items)", re.I)


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _classify(name: str, values: list[Any]) -> tuple[ColumnKind, ValueFormat]:
    present = [v for v in values if v is not None]
    if not present:
        return "text", "text"
    if all(isinstance(v, bool) for v in present):
        return "boolean", "text"

    if all(_is_number(v) for v in present):
        if _ID_NAME.search(name):
            return "identifier", "integer"
        # Year / month-number columns are time dimensions, not measures.
        if _TEMPORAL_NAME.search(name) and all(isinstance(v, int) for v in present):
            return "temporal", "integer"
        if _PERCENT_NAME.search(name) and not _CURRENCY_NAME.search(name):
            return "numeric", "percent"
        if _CURRENCY_NAME.search(name) and not _COUNT_NAME.search(name):
            return "numeric", "currency"
        if all(isinstance(v, int) for v in present):
            return "numeric", "integer"
        return "numeric", "number"

    strings = [str(v) for v in present]
    if all(_DATE_RE.match(s) for s in strings):
        return "temporal", "date"
    if all(_PERIOD_RE.match(s) or s.lower() in _MONTH_NAMES for s in strings):
        return "temporal", "text"
    if _ID_NAME.search(name):
        return "identifier", "text"
    distinct = len(set(strings))
    avg_len = sum(len(s) for s in strings) / len(strings)
    if avg_len > 60 and distinct == len(strings):
        return "text", "text"
    return "categorical", "text"


def profile_columns(columns: list[str], rows: list[list[Any]]) -> list[ColumnMeta]:
    metas = []
    for idx, name in enumerate(columns):
        values = [row[idx] for row in rows]
        kind, fmt = _classify(name, values)
        metas.append(
            ColumnMeta(
                name=name,
                kind=kind,
                format=fmt,
                distinct_count=len({str(v) for v in values if v is not None}),
                null_count=sum(1 for v in values if v is None),
            )
        )
    return metas
