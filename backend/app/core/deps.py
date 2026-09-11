import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedException
from app.core.security import decode_token
from app.models.user import User
from app.repositories.user import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode the Bearer access token and return the authenticated user.

    Deliberately does NOT use AuthService — token introspection is a
    read-only concern that belongs in the dependency layer, not the
    business-logic layer (which handles login/register/refresh).
    """
    if credentials is None:
        raise UnauthorizedException(detail="Not authenticated")

    payload = decode_token(credentials.credentials, token_type="access")
    if payload is None:
        raise UnauthorizedException(detail="Invalid or expired token")

    raw_id = payload.get("sub")
    try:
        user_id = uuid.UUID(str(raw_id))
    except (ValueError, TypeError):
        raise UnauthorizedException(detail="Invalid token payload")

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise UnauthorizedException(detail="User not found")
    if not user.is_active:
        raise UnauthorizedException(detail="User account is inactive")

    return user
