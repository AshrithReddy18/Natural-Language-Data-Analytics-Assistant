"""Upgrading an existing SQLite metadata store must keep its data.

SQLite migrations rebuild tables (copy, drop, rename). With foreign keys enforced, dropping the old
`data_sources` table would cascade and delete every conversation, message and query run.
"""

import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from app.core.config import BACKEND_DIR, get_settings
from app.models import database


@pytest.fixture
def metadata_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "meta.db"
    monkeypatch.setattr(get_settings(), "database_url", f"sqlite:///{path.as_posix()}")
    database.get_engine.cache_clear()
    yield path
    database.get_engine().dispose()
    database.get_engine.cache_clear()


def _alembic() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def test_upgrade_keeps_existing_conversations(metadata_db: Path) -> None:
    command.upgrade(_alembic(), "0001")
    with sqlite3.connect(metadata_db) as conn:
        conn.execute(
            "INSERT INTO data_sources (id, name, kind, encrypted_url, display_url, currency, is_demo, created_at) "
            "VALUES ('ds1', 'Demo', 'sqlite', 'x', 'x', 'INR', 1, '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO conversations (id, title, data_source_id, created_at, updated_at) "
            "VALUES ('c1', 'Revenue by city?', 'ds1', '2026-01-01', '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, created_at) "
            "VALUES ('m1', 'c1', 'user', 'Revenue by city?', '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO query_runs (id, data_source_id, conversation_id, source, status, attempts, created_at) "
            "VALUES ('r1', 'ds1', 'c1', 'chat', 'success', 1, '2026-01-01')"
        )

    command.upgrade(_alembic(), "head")

    with sqlite3.connect(metadata_db) as conn:
        counts = [
            conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("conversations", "messages", "query_runs")
        ]
        assert counts == [1, 1, 1]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
