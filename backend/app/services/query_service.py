"""SQL workbench: analysts can write SQL by hand; it goes through the same safety and
analytics layers as model-generated SQL (validation → read-only execution → chart → facts)."""

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.entities import DataSource, QueryRun, User
from app.repositories.repositories import QueryRunRepository
from app.schemas.analysis import AnalysisResult, ErrorInfo, SQLAttempt, SQLInfo, ValidationInfo
from app.schemas.api import QueryRunOut, QueryValidateResponse
from app.services import schema_service
from app.services.analysis_pipeline import AnalysisPipeline
from app.services.datasource_service import DataSourceService, connector_for
from app.services.query_executor import QueryExecutor
from app.services.sql_validator import SQLValidator, ValidationResult


def _validation_info(v: ValidationResult) -> ValidationInfo:
    return ValidationInfo(ok=v.ok, errors=v.errors, warnings=v.warnings, limit_applied=v.limit_applied, tables=v.tables)


class QueryService:
    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user
        self.sources = DataSourceService(db, user)
        self.runs = QueryRunRepository(db)

    def _validator(self, source_id: str) -> tuple[SQLValidator, DataSource]:
        source = self.sources.get(source_id)
        connector = connector_for(source)
        snapshot = schema_service.get_schema(source.id, connector)
        return SQLValidator(snapshot, max_rows=get_settings().max_result_rows), source

    def validate(self, source_id: str, sql: str) -> QueryValidateResponse:
        validator, _ = self._validator(source_id)
        v = validator.validate(sql)
        return QueryValidateResponse(validated_sql=v.validated_sql, validation=_validation_info(v))

    def execute(self, source_id: str, sql: str) -> AnalysisResult:
        settings = get_settings()
        validator, source = self._validator(source_id)
        connector = connector_for(source)
        result = AnalysisResult(
            status="error", question="SQL workbench query", title="Query result", currency=source.currency
        )
        v = validator.validate(sql)
        sql_info = result.sql = SQLInfo(
            dialect=connector.dialect_label,
            generated_sql=sql,
            validated_sql=v.validated_sql,
            validation=_validation_info(v),
        )
        if not v.ok:
            sql_info.attempts = [SQLAttempt(sql=sql, stage="validation", error=v.error_message)]
            result.error = ErrorInfo(code="sql_invalid", message=v.error_message)
        else:
            try:
                data = QueryExecutor(
                    connector, timeout_s=settings.query_timeout_seconds, max_rows=settings.max_result_rows
                ).execute(v)
                sql_info.attempts = [SQLAttempt(sql=v.validated_sql or sql, stage="success")]
                pipeline = AnalysisPipeline(
                    settings=settings, source_id=source.id, connector=connector, provider=None, currency=result.currency
                )
                result = pipeline.analyze(result, data, use_llm=False)
            except AppError as exc:
                sql_info.attempts = [SQLAttempt(sql=v.validated_sql or sql, stage="execution", error=exc.message)]
                result.error = ErrorInfo(code=exc.code, message=exc.message)

        status = (
            "success"
            if result.status in ("success", "empty")
            else ("timeout" if result.error and result.error.code == "query_timeout" else "failed")
        )
        run = self.runs.add(
            QueryRun(
                owner_id=self.user.id,
                data_source_id=source_id,
                source="workbench",
                question=None,
                generated_sql=sql,
                validated_sql=v.validated_sql,
                status=status,
                error_message=result.error.message if result.error else None,
                row_count=result.result.row_count if result.result else None,
                execution_ms=result.result.execution_ms if result.result else None,
            )
        )
        result.query_run_id = run.id
        return result

    def history(self, source_id: str | None, limit: int) -> list[QueryRunOut]:
        return [
            QueryRunOut.model_validate(r)
            for r in self.runs.recent(owner_id=self.user.id, data_source_id=source_id, limit=limit)
        ]
