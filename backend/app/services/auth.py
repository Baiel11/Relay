import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.core.exceptions import ConflictException, UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository

settings = get_settings()


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository,
    ) -> None:
        self.user_repo = user_repo
        self.token_repo = token_repo


    @staticmethod
    def _parse_user_id(payload: dict) -> uuid.UUID:
        raw = payload.get("sub")
        if raw is None:
            raise UnauthorizedException(detail="Invalid token payload")
        try:
            return uuid.UUID(str(raw))
        except ValueError:
            raise UnauthorizedException(detail="Invalid token payload")


    def _refresh_expires_at(self) -> datetime:
        return datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )


    async def register(self, email: str, username: str, password: str) -> User:
        existing = await self.user_repo.get_by_email_or_username(email, username)
        if existing:
            raise ConflictException(detail="Email or username already taken")
        return await self.user_repo.create(email, username, hash_password(password))


    async def login(self, email: str, password: str) -> tuple[str, str]:
        """
        Authenticate and return (access_token, refresh_token).
        The refresh token's JTI is persisted to the DB.
        """
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedException(detail="Invalid email or password")

        access_token, _ = create_access_token(str(user.id))
        refresh_token, jti = create_refresh_token(str(user.id))

        await self.token_repo.create(
            jti=jti,
            user_id=user.id,
            expires_at=self._refresh_expires_at(),
        )

        return access_token, refresh_token


    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        """
        Validate the refresh token against the DB (checks revocation),
        revoke the old JTI, issue and persist a fresh pair.
        """
        payload = decode_token(refresh_token, token_type="refresh")
        if payload is None:
            raise UnauthorizedException(detail="Invalid or expired refresh token")

        jti = payload.get("jti")
        if not jti:
            raise UnauthorizedException(detail="Malformed refresh token")

        stored = await self.token_repo.get_by_jti(jti)
        if stored is None or not stored.is_valid:
            raise UnauthorizedException(
                detail="Refresh token has been revoked or expired"
            )

        user_id = self._parse_user_id(payload)
        user = await self.user_repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedException(detail="User not found or inactive")

        # Rotate: revoke the old token, create a new one
        await self.token_repo.revoke(jti)

        new_access_token, _ = create_access_token(str(user.id))
        new_refresh_token, new_jti = create_refresh_token(str(user.id))

        await self.token_repo.create(
            jti=new_jti,
            user_id=user.id,
            expires_at=self._refresh_expires_at(),
        )

        return new_access_token, new_refresh_token


    async def logout(self, refresh_token: str) -> uuid.UUID | None:
        """Revoke a single refresh token server-side and return user_id."""
        payload = decode_token(refresh_token, token_type="refresh")
        if payload is None:
            return None

        jti = payload.get("jti")
        if jti:
            await self.token_repo.revoke(jti)

        try:
            return self._parse_user_id(payload)
        except UnauthorizedException:
            return None


    async def logout_all(self, user_id: uuid.UUID) -> None:
        """Revoke all refresh tokens for a user (logout from every device)."""
        await self.token_repo.revoke_all_for_user(user_id)
