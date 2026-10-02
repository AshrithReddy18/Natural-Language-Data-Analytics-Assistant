from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.entities import User
from app.schemas.analysis import AnalysisResult
from app.schemas.api import QueryRequest, QueryRunOut, QueryValidateResponse
from app.services.query_service import QueryService

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/validate", response_model=QueryValidateResponse)
def validate_query(
    body: QueryRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> QueryValidateResponse:
    return QueryService(db, user).validate(body.data_source_id, body.sql)


@router.post("/execute", response_model=AnalysisResult)
def execute_query(
    body: QueryRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> AnalysisResult:
    return QueryService(db, user).execute(body.data_source_id, body.sql)


@router.get("/history", response_model=list[QueryRunOut])
def query_history(
    data_source_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[QueryRunOut]:
    return QueryService(db, user).history(data_source_id, limit)
