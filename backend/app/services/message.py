import uuid

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import BadRequestException
from app.models.message import Message
from app.repositories.message import MessageRepository
from app.schemas.message import MessageListResponse


class MessageService:
    def __init__(self, message_repo: MessageRepository):
        self.message_repo = message_repo


    async def send_message(
        self,
        conversation_id: uuid.UUID,
        sender_id: uuid.UUID,
        content: str,
        client_message_id: uuid.UUID | None = None,
    ) -> tuple[Message, bool]:
        client_message_id = client_message_id or uuid.uuid4()

        existing = await self.message_repo.get_by_client_message_id(
            sender_id, client_message_id
        )
        if existing:
            if existing.conversation_id != conversation_id:
                raise BadRequestException(
                    detail="client_message_id already used in another conversation"
                )
            return existing, False

        try:
            message = await self.message_repo.create(
                conversation_id, sender_id, content, client_message_id
            )
        except IntegrityError:
            await self.message_repo.db.rollback()
            existing = await self.message_repo.get_by_client_message_id(
                sender_id, client_message_id
            )
            if existing is None or existing.conversation_id != conversation_id:
                raise BadRequestException(
                    detail="client_message_id already used in another conversation"
                )
            return existing, False

        return message, True


    async def list_messages(
        self,
        conversation_id: uuid.UUID,
        limit: int = 50,
        before: uuid.UUID | None = None,
    ) -> MessageListResponse:
        cursor: Message | None = None
        if before is not None:
            cursor = await self.message_repo.get_by_id(before)
            if cursor is None or cursor.conversation_id != conversation_id:
                raise BadRequestException(detail="Invalid pagination cursor")

        messages = await self.message_repo.list(
            conversation_id, limit=limit + 1, before=cursor
        )
        has_more = len(messages) > limit
        return MessageListResponse.model_validate(
            {
                "items": messages[:limit],
                "has_more": has_more,
            }
        )


    async def backfill(
        self,
        conversation_id: uuid.UUID,
        after_message_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> MessageListResponse:
        cursor: Message | None = None
        if after_message_id is not None:
            cursor = await self.message_repo.get_by_id(after_message_id)
            if cursor is None or cursor.conversation_id != conversation_id:
                raise BadRequestException(detail="Invalid pagination cursor")

        messages = await self.message_repo.list_after(
            conversation_id, limit=limit + 1, after=cursor
        )
        has_more = len(messages) > limit
        return MessageListResponse.model_validate(
            {
                "items": messages[:limit],
                "has_more": has_more,
            }
        )