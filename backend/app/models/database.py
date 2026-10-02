"""Engine and session factory for DataPilot's own metadata store (not the analysed databases)."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import DATA_DIR, get_settings
from app.core.urls import normalize_db_url


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if url.startswith("sqlite"):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # type: ignore[no-untyped-def]
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        return engine
    # No server-side prepared statements: hosted Postgres often sits behind a transaction-mode
    # connection pooler (e.g. Neon's), where they can fail between transactions.
    return create_engine(normalize_db_url(url), pool_pre_ping=True, connect_args={"prepare_threshold": None})


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
