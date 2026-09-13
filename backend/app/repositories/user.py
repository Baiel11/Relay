import uuid

from sqlalchemy import case, func, or_, select
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
        clean_q = query.strip()
        if not clean_q:
            return PagedResult(items=[], total=0)

        prefix_pattern = f"{clean_q}%"
        substr_pattern = f"%{clean_q}%"

        if len(clean_q) == 1:
            where = or_(
                User.username.ilike(prefix_pattern),
                User.email.ilike(prefix_pattern),
            )
        else:
            where = or_(
                User.username.ilike(prefix_pattern),
                User.email.ilike(prefix_pattern),
                User.username.ilike(substr_pattern),
                User.email.ilike(substr_pattern),
            )


        prefix_rank = case(
            (User.username.ilike(prefix_pattern), 0),
            (User.email.ilike(prefix_pattern), 1),
            (User.username.ilike(substr_pattern), 2),
            else_=3,
        )

        count_result = await self.db.execute(
            select(func.count()).select_from(User).where(where)
        )
        total = count_result.scalar_one()

        items_result = await self.db.execute(
            select(User)
            .where(where)
            .order_by(prefix_rank, User.username.asc())
            .limit(limit)
            .offset(offset)
        )
        items = list(items_result.scalars().all())

        return PagedResult(items=items, total=total)


    async def create(self, email: str, username: str, hashed_password: str) -> User:
        user = User(email=email, username=username, hashed_password=hashed_password)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
