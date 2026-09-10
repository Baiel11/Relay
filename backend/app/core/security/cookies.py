from fastapi import Request, Response

from app.core.config import get_settings

settings = get_settings()

SECURE_COOKIES = not settings.debug


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path=settings.refresh_cookie_path,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite=settings.cookie_samesite,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.refresh_cookie_path,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite=settings.cookie_samesite,
    )


def extract_refresh_token(request: Request, fallback_token: str | None = None) -> str:
    token = request.cookies.get(settings.refresh_cookie_name) or fallback_token
    if not token:
        raise ValueError("Refresh token missing")
    return token
