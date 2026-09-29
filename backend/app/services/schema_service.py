"""Schema discovery, caching, and selection of the schema context sent to the LLM."""

import re
import threading
import time
from collections import deque

from app.datasources.base import Connector, SchemaSnapshot, TableInfo

_CACHE_TTL_S = 600
_cache: dict[str, tuple[float, SchemaSnapshot]] = {}
_lock = threading.Lock()

# A few business words that rarely appear verbatim in column names.
_SYNONYMS = {
    "revenue": {"amount", "total", "price", "sales", "line_total", "order"},
    "sales": {"order", "amount", "revenue", "line_total"},
    "sold": {"quantity", "order"},
    "buyer": {"customer"},
    "client": {"customer"},
    "purchase": {"order"},
    "item": {"product", "order_item"},
    "spend": {"amount", "payment"},
    "aov": {"order", "amount", "line_total"},
    "region": {"city", "state", "region"},
}


def get_schema(source_id: str, connector: Connector, *, refresh: bool = False) -> SchemaSnapshot:
    now = time.monotonic()
    with _lock:
        cached = _cache.get(source_id)
        if cached and not refresh and now - cached[0] < _CACHE_TTL_S:
            return cached[1]
    snapshot = connector.introspect()
    with _lock:
        _cache[source_id] = (now, snapshot)
    return snapshot


def invalidate(source_id: str) -> None:
    with _lock:
        _cache.pop(source_id, None)


def _tokens(text: str) -> set[str]:
    words = {w.rstrip("s") for w in re.findall(r"[a-z0-9_]+", text.lower()) if len(w) > 2}
    expanded = set(words)
    for w in words:
        expanded |= _SYNONYMS.get(w, set())
    return expanded


def _score(table: TableInfo, tokens: set[str]) -> float:
    score = 0.0
    name = table.name.lower().rstrip("s")
    if name in tokens or any(name in t or t in name for t in tokens if len(t) > 3):
        score += 3
    for col in table.columns:
        cname = col.name.lower()
        parts = set(cname.split("_")) | {cname}
        if parts & tokens:
            score += 1
        for value in col.sample_values or []:
            if value.lower().rstrip("s") in tokens:
                score += 2
    return score


def select_tables(schema: SchemaSnapshot, text: str, budget: int) -> list[TableInfo]:
    """All tables for small schemas; otherwise the most relevant tables plus join paths."""
    if len(schema.tables) <= budget:
        return schema.tables
    tokens = _tokens(text)
    ranked = sorted(schema.tables, key=lambda t: _score(t, tokens), reverse=True)
    chosen = {t.name for t in ranked[: max(1, budget // 2)] if _score(t, tokens) > 0}
    if not chosen:
        return ranked[:budget]

    # Add tables needed to join the chosen ones (shortest FK paths).
    graph: dict[str, set[str]] = {t.name: set() for t in schema.tables}
    for rel in schema.relationships:
        graph[rel.from_table].add(rel.to_table)
        graph[rel.to_table].add(rel.from_table)
    anchor = next(iter(chosen))
    for target in list(chosen):
        path = _shortest_path(graph, anchor, target)
        chosen.update(path)
    return [t for t in schema.tables if t.name in chosen][:budget]


def _shortest_path(graph: dict[str, set[str]], start: str, goal: str) -> list[str]:
    queue: deque[list[str]] = deque([[start]])
    seen = {start}
    while queue:
        path = queue.popleft()
        if path[-1] == goal:
            return path
        for nxt in graph.get(path[-1], ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append([*path, nxt])
    return []


def render_schema(tables: list[TableInfo]) -> str:
    """Compact, model-friendly schema description."""
    lines: list[str] = []
    for table in tables:
        rows = f" (~{table.row_count:,} rows)" if table.row_count is not None else ""
        lines.append(f"Table {table.name}{rows}")
        for col in table.columns:
            notes = []
            if col.primary_key:
                notes.append("primary key")
            if col.references:
                notes.append(f"references {col.references}")
            if col.sample_values:
                values = ", ".join(f"'{v}'" for v in col.sample_values)
                notes.append(f"values: {values}")
            if col.value_range:
                notes.append(f"range {col.value_range[0]} to {col.value_range[1]}")
            suffix = f"  -- {'; '.join(notes)}" if notes else ""
            lines.append(f"  - {col.name} {col.type}{suffix}")
        lines.append("")
    return "\n".join(lines).strip()


def latest_data_date(tables: list[TableInfo]) -> str | None:
    """Most recent date in the data; used to anchor relative dates like "last month"."""
    ends = [c.value_range[1] for t in tables for c in t.columns if c.value_range]
    return max(ends)[:10] if ends else None
