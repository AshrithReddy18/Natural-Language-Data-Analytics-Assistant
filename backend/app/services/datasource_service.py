"""Registering, connecting to, and describing data sources."""

import logging
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import DATA_DIR, get_settings
from app.core.errors import AppError, BadRequestError, NotFoundError
from app.core.logging import log_event
from app.core.security import decrypt, encrypt, redact_url
from app.datasources.base import Connector, SchemaSnapshot
from app.datasources.registry import detect_kind, registry
from app.datasources.sqlalchemy_connector import SQLAlchemyConnector
from app.models.entities import DataSource
from app.repositories.repositories import DataSourceRepository
from app.schemas.api import (
    ColumnOut,
    DataSourceCreate,
    DataSourceOut,
    DataSourceUpdate,
    RelationshipOut,
    SchemaOut,
    TableOut,
)
from app.services import schema_service

logger = logging.getLogger(__name__)

DEMO_NOTES = """- Revenue means SUM(order_items.line_total) (already net of discounts) for orders whose
  status is 'delivered' or 'shipped'. "Gross revenue" / "GMV" includes every status.
  Cancelled and returned orders are excluded from revenue unless the user asks about them.
- An order's value is the sum of its order_items.line_total. Average order value (AOV) is
  revenue divided by the number of distinct revenue-counting orders.
- A repeat customer has more than one order (any status except 'cancelled').
- Customer location (city, state, region) lives on customers; product attributes on products.
- Profit for an item is line_total - quantity * products.unit_cost."""


def connector_for(source: DataSource) -> Connector:
    return registry.get(source.id, decrypt(source.encrypted_url))


def _validate_url(url: str) -> str:
    try:
        kind = detect_kind(url)
    except Exception as exc:
        raise BadRequestError(str(exc) if isinstance(exc, ValueError) else "Invalid connection URL.") from exc
    if kind == "sqlite":
        # Only files inside the server's data directory: no arbitrary filesystem access.
        path = Path(make_url(url).database or "").resolve()
        if DATA_DIR.resolve() not in path.parents:
            raise BadRequestError(f"SQLite files must be located in the server data directory ({DATA_DIR.name}/).")
    return kind


def to_out(source: DataSource, *, check: bool = False) -> DataSourceOut:
    out = DataSourceOut.model_validate(source)
    if check:
        try:
            snapshot = schema_service.get_schema(source.id, connector_for(source))
            out.status, out.table_count = "connected", len(snapshot.tables)
        except AppError as exc:
            out.status, out.status_message = "error", exc.message
    return out


class DataSourceService:
    def __init__(self, db: Session) -> None:
        self.repo = DataSourceRepository(db)

    def list(self) -> list[DataSourceOut]:
        return [to_out(s, check=True) for s in self.repo.all()]

    def get(self, source_id: str) -> DataSource:
        source = self.repo.get(source_id)
        if source is None:
            raise NotFoundError("Data source not found.")
        return source

    def create(self, data: DataSourceCreate) -> DataSourceOut:
        kind = _validate_url(data.url)
        source = DataSource(
            name=data.name.strip(),
            kind=kind,
            encrypted_url=encrypt(data.url),
            display_url=redact_url(data.url),
            description=data.description,
            business_notes=data.business_notes,
            currency=data.currency.upper(),
        )
        # Connect before saving so a bad URL never lands in the list.
        probe: SQLAlchemyConnector | None = None
        try:
            probe = SQLAlchemyConnector(data.url)
            probe.test_connection()
        except AppError as exc:
            raise BadRequestError(f"Could not connect: {exc.message}") from exc
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc
        finally:
            if probe:
                probe.dispose()
        self.repo.add(source)
        log_event(logger, "datasource_created", data_source_id=source.id, kind=kind)
        return to_out(source, check=True)

    def update(self, source_id: str, data: DataSourceUpdate) -> DataSourceOut:
        source = self.get(source_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(source, field, value.upper() if field == "currency" and value else value)
        self.repo.db.commit()
        return to_out(source, check=True)

    def delete(self, source_id: str) -> None:
        source = self.get(source_id)
        if source.is_demo:
            raise BadRequestError("The demo data source cannot be removed.")
        registry.evict(source.id)
        schema_service.invalidate(source.id)
        self.repo.delete(source)

    def schema(self, source_id: str, *, refresh: bool = False) -> SchemaOut:
        source = self.get(source_id)
        snapshot = schema_service.get_schema(source.id, connector_for(source), refresh=refresh)
        return schema_to_out(source.id, snapshot)

    def ensure_demo(self) -> None:
        """Seed (if needed) and register the demo database configured by DEMO_DATABASE_URL."""
        settings = get_settings()
        url = settings.demo_database_url
        if not url:
            return
        from app.demo.seed import seed

        if url.startswith("sqlite"):
            DATA_DIR.mkdir(parents=True, exist_ok=True)
        # Seeding needs write access; querying uses DEMO_DATABASE_URL, which in Docker is a
        # read-only role, so the two can differ.
        counts = seed(settings.demo_seed_database_url or url, if_empty=True)
        if counts:
            log_event(logger, "demo_seeded", **counts)
        existing = self.repo.get_demo()
        if existing:
            if decrypt(existing.encrypted_url) != url:
                # Point the existing demo source at the new URL (keeps its conversations).
                registry.evict(existing.id)
                schema_service.invalidate(existing.id)
                existing.kind, existing.encrypted_url, existing.display_url = (
                    detect_kind(url),
                    encrypt(url),
                    redact_url(url),
                )
                self.repo.db.commit()
            return
        self.repo.add(
            DataSource(
                name=settings.demo_database_name,
                kind=detect_kind(url),
                encrypted_url=encrypt(url),
                display_url=redact_url(url),
                is_demo=True,
                currency="INR",
                description="Indian e-commerce store, Jan 2024 – Dec 2025: customers, products, orders, order items and payments.",
                business_notes=DEMO_NOTES,
            )
        )


def schema_to_out(source_id: str, snapshot: SchemaSnapshot) -> SchemaOut:
    return SchemaOut(
        data_source_id=source_id,
        dialect=snapshot.dialect,
        fetched_at=snapshot.fetched_at,
        tables=[
            TableOut(
                name=t.name,
                row_count=t.row_count,
                columns=[
                    ColumnOut(
                        name=c.name,
                        type=c.type,
                        nullable=c.nullable,
                        primary_key=c.primary_key,
                        references=c.references,
                        sample_values=c.sample_values,
                        value_range=list(c.value_range) if c.value_range else None,
                    )
                    for c in t.columns
                ],
            )
            for t in snapshot.tables
        ],
        relationships=[RelationshipOut(**vars(r)) for r in snapshot.relationships],
    )
