import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_read import ConversationRead
from app.models.message import Message


class ConversationReadRepository:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def upsert_last_read(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        read_time: datetime | None = None,
    ) -> datetime:
        """Record the timestamp up to which user has read messages in the conversation."""
        if read_time is None:
            read_time = datetime.now(timezone.utc)

        stmt = (
            insert(ConversationRead)
            .values(
                user_id=user_id,
                conversation_id=conversation_id,
                last_read_at=read_time,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "conversation_id"],
                set_={"last_read_at": read_time},
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()
        return read_time


    async def get_last_read(
        self, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> datetime | None:
        stmt = select(ConversationRead.last_read_at).where(
            ConversationRead.user_id == user_id,
            ConversationRead.conversation_id == conversation_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


    async def count_unread(
        self, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> int:
        """
        Count messages in conversation sent by others after user's last_read_at.
        This is the Postgres source-of-truth fallback if Redis keys are evicted.
        """
        last_read = await self.get_last_read(user_id, conversation_id)

        stmt = select(func.count()).select_from(Message).where(
            Message.conversation_id == conversation_id,
            Message.sender_id != user_id,
        )
        if last_read is not None:
            stmt = stmt.where(Message.created_at > last_read)

        result = await self.db.execute(stmt)
        return result.scalar_one()
