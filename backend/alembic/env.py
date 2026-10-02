"""Alembic environment for DataPilot's metadata store. The URL comes from app settings."""

from alembic import context
from app.models import entities  # noqa: F401  (registers models on Base.metadata)
from app.models.database import Base, get_engine

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=str(get_engine().url), target_metadata=target_metadata, literal_binds=True, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with get_engine().connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        if sqlite:
            # SQLite migrations rebuild tables (copy, drop, rename). With foreign keys enforced, the
            # drop cascades and deletes every row that references the table. The pragma has no
            # effect inside a transaction, so it is set before one begins.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        try:
            context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=sqlite)
            with context.begin_transaction():
                if connection.dialect.name == "postgresql":
                    # Several serverless instances can cold-start at once and each migrates on
                    # startup: take turns, so later ones find the schema already up to date.
                    connection.exec_driver_sql("SELECT pg_advisory_xact_lock(7290001)")
                context.run_migrations()
            if sqlite:
                broken = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
                if broken:
                    raise RuntimeError(f"Migration left rows with broken foreign keys: {broken[:5]}")
        finally:
            if sqlite:
                connection.commit()
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
