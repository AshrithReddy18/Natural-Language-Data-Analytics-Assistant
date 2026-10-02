"""Registering, connecting to, and describing data sources."""

import logging
import os
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import DATA_DIR, get_settings
from app.core.errors import AppError, BadRequestError, ForbiddenError, NotFoundError
from app.core.logging import log_event
from app.core.security import decrypt, encrypt, redact_url
from app.datasources.base import Connector, SchemaSnapshot
from app.datasources.registry import detect_kind, registry
from app.datasources.sqlalchemy_connector import SQLAlchemyConnector
from app.datasources.uploads import build_sqlite, describe, parse_files
from app.models.entities import DataSource, User
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


# (filename, content) pairs. Named at module level: inside DataSourceService, `list` is a method.
UploadedFiles = list[tuple[str, bytes]]


def _upload_path(source: DataSource) -> Path:
    return DATA_DIR / "uploads" / f"{source.id}.db"


def _materialize_upload(source: DataSource) -> str:
    """The SQLite URL for an uploaded source, writing its stored database to disk if this server
    instance doesn't have it yet (serverless instances start with an empty disk)."""
    path = _upload_path(source)
    if not path.is_file():
        if not source.upload_data:
            raise NotFoundError("The uploaded data for this source is missing.")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_bytes(source.upload_data)
        os.replace(tmp, path)
    return f"sqlite:///{path.as_posix()}"


def connector_for(source: DataSource) -> Connector:
    if source.kind == "upload":
        return registry.get(source.id, _materialize_upload(source))
    return registry.get(source.id, decrypt(source.encrypted_url))


def _validate_url(url: str) -> str:
    try:
        kind = detect_kind(url)
    except Exception as exc:
        raise BadRequestError(str(exc) if isinstance(exc, ValueError) else "Invalid connection URL.") from exc
    if kind == "sqlite":
        # Server files are off limits (including other users' uploads): files arrive by upload.
        raise BadRequestError("SQLite files can't be connected by path. Upload your data as CSV or Excel instead.")
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
    """Data sources as seen by one user: the shared demo plus their own. The user is None only
    for startup tasks (demo setup), which never call the per-user methods."""

    def __init__(self, db: Session, user: User | None = None) -> None:
        self.repo = DataSourceRepository(db)
        self.user = user

    @property
    def _owner_id(self) -> str:
        assert self.user is not None, "DataSourceService needs a user for per-user operations"
        return self.user.id

    def list(self) -> list[DataSourceOut]:
        return [to_out(s, check=True) for s in self.repo.visible_to(self._owner_id)]

    def get(self, source_id: str) -> DataSource:
        source = self.repo.get(source_id)
        # Someone else's source is reported as missing, not forbidden: its existence isn't theirs to know.
        if source is None or not (source.is_demo or source.owner_id == self._owner_id):
            raise NotFoundError("Data source not found.")
        return source

    def _get_own(self, source_id: str) -> DataSource:
        source = self.get(source_id)
        if source.is_demo:
            raise ForbiddenError("The shared demo data source can't be changed.")
        return source

    def create_upload(
        self, *, name: str, files: UploadedFiles, description: str | None, currency: str
    ) -> DataSourceOut:
        tables = parse_files(files)
        filenames = ", ".join(f for f, _ in files)
        source = DataSource(
            owner_id=self._owner_id,
            name=name.strip()[:120] or Path(files[0][0]).stem,
            kind="upload",
            encrypted_url=encrypt("upload"),
            display_url=f"Uploaded: {filenames}"[:500],
            description=description or describe(tables)[:1000],
            currency=currency.upper(),
            upload_data=build_sqlite(tables),
        )
        self.repo.add(source)
        log_event(logger, "datasource_uploaded", data_source_id=source.id, tables=len(tables))
        return to_out(source, check=True)

    def create(self, data: DataSourceCreate) -> DataSourceOut:
        kind = _validate_url(data.url)
        source = DataSource(
            owner_id=self._owner_id,
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
        source = self._get_own(source_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(source, field, value.upper() if field == "currency" and value else value)
        self.repo.db.commit()
        return to_out(source, check=True)

    def delete(self, source_id: str) -> None:
        source = self._get_own(source_id)
        registry.evict(source.id)
        schema_service.invalidate(source.id)
        if source.kind == "upload":
            _upload_path(source).unlink(missing_ok=True)
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
