"""Encryption for stored connection strings, and redaction for anything displayed or logged."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.engine import make_url

from app.core.config import get_settings


def _fernet() -> Fernet:
    secret = get_settings().secret_key.get_secret_value().encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:  # secret key rotated or data corrupted
        raise ValueError("Stored credentials could not be decrypted") from exc


def redact_url(url: str) -> str:
    """Render a SQLAlchemy URL with the password hidden, e.g. postgresql://user:***@host/db."""
    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return "<unparseable url>"
