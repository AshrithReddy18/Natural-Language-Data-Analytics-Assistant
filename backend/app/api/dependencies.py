from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.auth import SESSION_COOKIE, read_session_token
from app.core.errors import UnauthorizedError
from app.models.database import get_db
from app.models.entities import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = read_session_token(request.cookies.get(SESSION_COOKIE))
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise UnauthorizedError()
    return user


__all__ = ["get_current_user", "get_db"]
