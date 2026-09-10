import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject,
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": subject,
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(
        payload, settings.jwt_refresh_secret_key, algorithm=settings.jwt_algorithm
    )


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
    except JWTError:
        return None
