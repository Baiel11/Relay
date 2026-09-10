from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import UnauthorizedException
from app.core.security import (
    clear_refresh_cookie,
    extract_refresh_token,
    set_refresh_cookie,
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(UserRepository(db))


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: RegisterRequest, auth_service: AuthService = Depends(get_auth_service)):
    return await auth_service.register(body.email, body.username, body.password)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response, auth_service: AuthService = Depends(get_auth_service)):
    access_token, refresh_token = await auth_service.login(body.email, body.password)
    set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, auth_service: AuthService = Depends(get_auth_service)):
    try:
        token = extract_refresh_token(request)
    except ValueError:
        raise UnauthorizedException(detail="Missing refresh token")

    access_token, new_refresh_token = await auth_service.refresh(token)
    set_refresh_cookie(response, new_refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response):
    clear_refresh_cookie(response)
    return MessageResponse(detail="Logged out")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user