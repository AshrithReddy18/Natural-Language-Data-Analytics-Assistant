"""Keeps one live connector per registered data source, created lazily."""

import threading

from app.datasources.base import Connector
from app.datasources.sqlalchemy_connector import SQLAlchemyConnector


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, Connector] = {}
        self._lock = threading.Lock()

    def get(self, source_id: str, url: str) -> Connector:
        with self._lock:
            connector = self._connectors.get(source_id)
            if connector is None:
                connector = SQLAlchemyConnector(url)
                self._connectors[source_id] = connector
            return connector

    def evict(self, source_id: str) -> None:
        with self._lock:
            connector = self._connectors.pop(source_id, None)
        if connector:
            connector.dispose()

    def clear(self) -> None:
        for source_id in list(self._connectors):
            self.evict(source_id)


registry = ConnectorRegistry()


def detect_kind(url: str) -> str:
    from sqlalchemy.engine import make_url

    backend = make_url(url).get_backend_name()
    if backend not in ("postgresql", "sqlite"):
        raise ValueError(f"Unsupported database type '{backend}'. Supported: PostgreSQL, SQLite.")
    return backend
