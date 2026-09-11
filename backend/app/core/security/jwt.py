import uuid
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import get_settings

settings = get_settings()


def create_access_token(subject: str) -> tuple[str, str]:
    """Return (encoded_token, jti)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    jti = str(uuid.uuid4())
    payload = {
        "sub": subject,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": expire,
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti


def create_refresh_token(subject: str) -> tuple[str, str]:
    """Return (encoded_token, jti)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.refresh_token_expire_days)
    jti = str(uuid.uuid4())
    payload = {
        "sub": subject,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": expire,
        "type": "refresh",
    }
    token = jwt.encode(
        payload, settings.jwt_refresh_secret_key, algorithm=settings.jwt_algorithm
    )
    return token, jti


def decode_token(token: str, token_type: str = "access") -> dict | None:
    secret = (
        settings.jwt_secret_key
        if token_type == "access"
        else settings.jwt_refresh_secret_key
    )
    try:
        payload = jwt.decode(token, secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != token_type:
            return None
        return payload
    except InvalidTokenError:
        return None
