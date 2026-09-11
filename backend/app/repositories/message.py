from __future__ import annotations

import uuid

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


class MessageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def get_by_id(self, message_id: uuid.UUID) -> Message | None:
        result = await self.db.execute(select(Message).where(Message.id == message_id))
        return result.scalar_one_or_none()


    async def get_by_client_message_id(
        self, sender_id: uuid.UUID, client_message_id: uuid.UUID
    ) -> Message | None:
        result = await self.db.execute(
            select(Message).where(
                Message.sender_id == sender_id,
                Message.client_message_id == client_message_id,
            )
        )
        return result.scalar_one_or_none()


    async def create(
        self,
        conversation_id: uuid.UUID,
        sender_id: uuid.UUID,
        content: str,
        client_message_id: uuid.UUID,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            client_message_id=client_message_id,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message


    async def list(
        self,
        conversation_id: uuid.UUID,
        limit: int,
        before: Message | None = None,
    ) -> list[Message]:
        stmt = select(Message).where(Message.conversation_id == conversation_id)
        if before is not None:
            stmt = stmt.where(
                tuple_(Message.created_at, Message.id)
                < (before.created_at, before.id)
            )
        stmt = (
            stmt.order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


    async def list_after(
        self,
        conversation_id: uuid.UUID,
        limit: int,
        after: Message | None = None,
    ) -> list[Message]:
        stmt = select(Message).where(Message.conversation_id == conversation_id)
        if after is not None:
            stmt = stmt.where(
                tuple_(Message.created_at, Message.id)
                > (after.created_at, after.id)
            )
        stmt = (
            stmt.order_by(Message.created_at.asc(), Message.id.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())