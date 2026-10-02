"""FastAPI application: wiring, middleware, error handling, startup."""

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import auth, chat, datasets, health, queries
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, log_event, request_id_var
from app.datasources.registry import registry
from app.models.database import get_session_factory

logger = logging.getLogger("app")


def run_migrations() -> None:
    from alembic.config import Config

    from alembic import command
    from app.core.config import BACKEND_DIR

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.run_migrations_on_startup:
        run_migrations()
    from app.services.datasource_service import DataSourceService

    with get_session_factory()() as db:
        try:
            DataSourceService(db).ensure_demo()
        except Exception:
            logger.exception("demo_setup_failed")
    log_event(
        logger, "startup", version=__version__, environment=settings.environment, llm_provider=settings.llm_provider
    )
    yield
    registry.clear()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DataPilot API",
        version=__version__,
        lifespan=lifespan,
        description="Natural-language analytics: question → SQL → data → chart → insight.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith("/api"):
            log_event(
                logger,
                "request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                ms=int((time.perf_counter() - started) * 1000),
                request_id=request_id,
            )
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", [])[1:])
        message = f"{field}: {first.get('msg', 'invalid value')}" if field else "Invalid request."
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_request", "message": message}})

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", exc_info=exc)
        return JSONResponse(
            status_code=500, content={"error": {"code": "internal_error", "message": "Something went wrong."}}
        )

    for router in (health.router, auth.router, datasets.router, chat.router, queries.router):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
