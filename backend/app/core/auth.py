"""Password hashing (scrypt) and signed session tokens. Standard library only.

A session token is `<user_id>.<expires_unix>.<signature>`, signed with an HMAC key derived from
SECRET_KEY. It lives in an HttpOnly cookie, so page scripts never see it. Tokens are stateless:
logging out clears the cookie, and rotating SECRET_KEY signs everyone out.
"""

import base64
import hashlib
import hmac
import secrets
import time

from app.core.config import get_settings

SESSION_COOKIE = "dp_session"
SESSION_TTL_SECONDS = 30 * 24 * 3600

_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **_SCRYPT)
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = _unb64(digest)
        actual = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def _signing_key() -> bytes:
    secret = get_settings().secret_key.get_secret_value().encode()
    return hashlib.sha256(b"datapilot-session:" + secret).digest()


def _sign(payload: str) -> str:
    return _b64(hmac.new(_signing_key(), payload.encode(), hashlib.sha256).digest())


def create_session_token(user_id: str, *, ttl: int = SESSION_TTL_SECONDS) -> str:
    payload = f"{user_id}.{int(time.time()) + ttl}"
    return f"{payload}.{_sign(payload)}"


def read_session_token(token: str | None) -> str | None:
    """The user id in a valid, unexpired token; otherwise None."""
    if not token or token.count(".") != 2:
        return None
    user_id, expires, signature = token.split(".")
    if not hmac.compare_digest(signature, _sign(f"{user_id}.{expires}")):
        return None
    try:
        if int(expires) < time.time():
            return None
    except ValueError:
        return None
    return user_id
