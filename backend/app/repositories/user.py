import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories import PagedResult


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()


    async def get_by_email_or_username(self, email: str, username: str) -> User | None:
        result = await self.db.execute(
            select(User).where((User.email == email) | (User.username == username))
        )
        return result.scalar_one_or_none()


    async def search(
        self, query: str, limit: int = 20, offset: int = 0
    ) -> PagedResult[User]:
        pattern = f"%{query}%"
        where = or_(
            User.username.ilike(pattern),
            User.email.ilike(pattern),
        )

        count_result = await self.db.execute(
            select(func.count()).select_from(User).where(where)
        )
        total = count_result.scalar_one()

        items_result = await self.db.execute(
            select(User).where(where).order_by(User.username).limit(limit).offset(offset)
        )
        items = list(items_result.scalars().all())

        return PagedResult(items=items, total=total)


    async def create(self, email: str, username: str, hashed_password: str) -> User:
        user = User(email=email, username=username, hashed_password=hashed_password)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
