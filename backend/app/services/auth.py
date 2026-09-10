import uuid

from app.core.exceptions import ConflictException, UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user import UserRepository


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo


    @staticmethod
    def _parse_user_id(payload: dict) -> uuid.UUID:
        raw = payload.get("sub")
        if raw is None:
            raise UnauthorizedException(detail="Invalid token payload")
        try:
            return uuid.UUID(str(raw))
        except ValueError:
            raise UnauthorizedException(detail="Invalid token payload")


    async def get_current_user(self, token: str) -> User:
        payload = decode_token(token, token_type="access")
        if payload is None:
            raise UnauthorizedException(detail="Invalid or expired token")

        user_id = self._parse_user_id(payload)
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise UnauthorizedException(detail="User not found")

        if not user.is_active:
            raise UnauthorizedException(detail="User account is inactive")

        return user


    async def register(self, email: str, username: str, password: str) -> User:
        existing = await self.user_repo.get_by_email_or_username(email, username)
        if existing:
            raise ConflictException(detail="Email or username already taken")
        return await self.user_repo.create(email, username, hash_password(password))


    async def login(self, email: str, password: str) -> tuple[str, str]:
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedException(detail="Invalid email or password")
        return create_access_token(str(user.id)), create_refresh_token(str(user.id))


    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        payload = decode_token(refresh_token, token_type="refresh")
        if payload is None:
            raise UnauthorizedException(detail="Invalid or expired refresh token")

        user_id = self._parse_user_id(payload)
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedException(detail="User not found")

        return create_access_token(str(user.id)), create_refresh_token(str(user.id))
