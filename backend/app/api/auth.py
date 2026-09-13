from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import UnauthorizedException
from app.core.security import (
    clear_refresh_cookie,
    extract_refresh_token,
    set_refresh_cookie,
)
from app.models.user import User
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.auth import AuthService
from app.services.connection_manager import connection_manager
from app.services.redis.presence import presence_service
from app.services.redis.pubsub import pubsub_manager
from app.services.redis.rate_limiter import rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(
        user_repo=UserRepository(db),
        token_repo=RefreshTokenRepository(db),
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    dependencies=[Depends(rate_limit(limit=5, window_seconds=60))],
)
async def register(
    body: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    return await auth_service.register(body.email, body.username, body.password)


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(limit=10, window_seconds=60))],
)
async def login(
    body: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):

    access_token, refresh_token = await auth_service.login(body.email, body.password)
    set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        token = extract_refresh_token(request)
    except ValueError:
        raise UnauthorizedException(detail="Missing refresh token")

    access_token, new_refresh_token = await auth_service.refresh(token)
    set_refresh_cookie(response, new_refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Revoke the current refresh token server-side and clear the cookie."""
    try:
        token = extract_refresh_token(request)
        user_id = await auth_service.logout(token)
        if user_id:
            await presence_service.set_offline(user_id)
            await connection_manager.close_user_connections(user_id)
            await connection_manager.broadcast_presence(user_id, "offline")
            await pubsub_manager.publish_event(
                "presence", {"user_id": str(user_id), "status": "offline"}
            )
    except ValueError:
        pass

    clear_refresh_cookie(response)
    return MessageResponse(detail="Logged out")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    response: Response,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Revoke all refresh tokens for the current user (all devices)."""
    await auth_service.logout_all(current_user.id)
    await presence_service.set_offline(current_user.id)
    await connection_manager.close_user_connections(current_user.id)
    await connection_manager.broadcast_presence(current_user.id, "offline")
    await pubsub_manager.publish_event(
        "presence", {"user_id": str(current_user.id), "status": "offline"}
    )
    clear_refresh_cookie(response)
    return MessageResponse(detail="Logged out from all devices")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user