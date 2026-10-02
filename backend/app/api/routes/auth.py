from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.auth import SESSION_COOKIE, SESSION_TTL_SECONDS, create_session_token, hash_password, verify_password
from app.core.config import get_settings
from app.core.errors import ConflictError, UnauthorizedError
from app.models.entities import Conversation, DataSource, QueryRun, User
from app.schemas.api import LoginRequest, SignupRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _start_session(response: Response, user: User) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user.id),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=get_settings().environment == "production",
        path="/",
    )


def _claim_unowned(db: Session, user: User) -> None:
    """Hand data created before accounts existed to the first account, so it isn't orphaned."""
    for model in (DataSource, Conversation, QueryRun):
        stmt = update(model).where(model.owner_id.is_(None)).values(owner_id=user.id)
        if model is DataSource:
            stmt = stmt.where(DataSource.is_demo.is_(False))
        db.execute(stmt)


@router.post("/signup", response_model=UserOut, status_code=201)
def signup(body: SignupRequest, response: Response, db: Session = Depends(get_db)) -> User:
    email = body.email
    if db.scalars(select(User).where(User.email == email)).first():
        raise ConflictError("An account with this email already exists. Sign in instead.")
    first = not db.scalar(select(func.count()).select_from(User))
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    if first:
        _claim_unowned(db, user)
    db.commit()
    _start_session(response, user)
    return user


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> User:
    user = db.scalars(select(User).where(User.email == body.email)).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise UnauthorizedError("Incorrect email or password.")
    _start_session(response, user)
    return user


@router.post("/logout", status_code=204)
def logout() -> Response:
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
