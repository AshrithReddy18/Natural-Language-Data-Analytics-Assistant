from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.api.dependencies import get_db
from app.llm.factory import llm_status
from app.schemas.api import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    configured, provider, model = llm_status()
    return HealthOut(
        status="ok" if db_ok else "degraded",
        version=__version__,
        database=db_ok,
        llm_configured=configured,
        llm_provider=provider,
        llm_model=model,
    )
