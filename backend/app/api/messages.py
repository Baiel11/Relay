import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.conversations import get_conversation_service
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.repositories.message import MessageRepository
from app.schemas.message import MessageCreate, MessageListResponse, MessageResponse
from app.services.conversation import ConversationService
from app.services.message import MessageService

router = APIRouter(
    prefix="/conversations/{conversation_id}/messages", tags=["messages"]
)


def get_message_service(db: AsyncSession = Depends(get_db)) -> MessageService:
    return MessageService(MessageRepository(db))


@router.post("", response_model=MessageResponse)
async def send_message(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    response: Response,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
    message_service: MessageService = Depends(get_message_service),
):
    await conversation_service.get_for_user(conversation_id, current_user.id)
    message, created = await message_service.send_message(
        conversation_id,
        current_user.id,
        body.content,
        body.client_message_id,
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return message


@router.get("", response_model=MessageListResponse)
async def list_messages(
    conversation_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    before: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
    message_service: MessageService = Depends(get_message_service),
):
    await conversation_service.get_for_user(conversation_id, current_user.id)
    return await message_service.list_messages(conversation_id, limit, before)