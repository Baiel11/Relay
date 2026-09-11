import uuid
from dataclasses import dataclass
from typing import Generic, TypeVar

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation

T = TypeVar("T")


@dataclass
class PagedResult(Generic[T]):
    items: list[T]
    total: int


class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def get_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()


    async def get_by_pair(
        self, user_a: uuid.UUID, user_b: uuid.UUID
    ) -> Conversation | None:
        a, b = Conversation.normalize_pair(user_a, user_b)
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.participant_a == a,
                Conversation.participant_b == b,
            )
        )
        return result.scalar_one_or_none()


    async def create(self, user_a: uuid.UUID, user_b: uuid.UUID) -> Conversation:
        a, b = Conversation.normalize_pair(user_a, user_b)
        conversation = Conversation(participant_a=a, participant_b=b)
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation


    async def list_for_user(
        self, user_id: uuid.UUID, limit: int, offset: int
    ) -> PagedResult[Conversation]:
        where = or_(
            Conversation.participant_a == user_id,
            Conversation.participant_b == user_id,
        )

        total_result = await self.db.execute(
            select(func.count()).select_from(Conversation).where(where)
        )
        total = total_result.scalar_one()

        items_result = await self.db.execute(
            select(Conversation)
            .where(where)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items = list(items_result.scalars().all())

        return PagedResult(items=items, total=total)