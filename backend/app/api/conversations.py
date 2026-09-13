import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.repositories.conversation import ConversationRepository
from app.repositories.conversation_read import ConversationReadRepository
from app.repositories.user import UserRepository
from app.schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
)
from app.services.conversation import ConversationService
from app.services.redis.pubsub import pubsub_manager
from app.services.redis.unread import unread_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


def get_conversation_service(db: AsyncSession = Depends(get_db)) -> ConversationService:
    return ConversationService(
        ConversationRepository(db),
        UserRepository(db),
        ConversationReadRepository(db),
    )


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    body: ConversationCreate,
    response: Response,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    data, created = await conversation_service.get_or_create(
        current_user.id, body.other_user_id
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return data


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    return await conversation_service.list_for_user(current_user.id, limit, offset)


@router.post("/{conversation_id}/read", status_code=status.HTTP_200_OK)
async def mark_conversation_read(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """Mark all messages up to now as read in PostgreSQL and reset Redis unread counter."""
    await conversation_service.get_for_user(conversation_id, current_user.id)
    read_time = datetime.now(timezone.utc)

    read_repo = ConversationReadRepository(db)
    await read_repo.upsert_last_read(current_user.id, conversation_id, read_time)
    await unread_service.reset_unread(current_user.id, conversation_id)

    # Publish read_receipt via Pub/Sub so sender sees read status
    await pubsub_manager.publish_event(
        "read_receipt",
        {
            "conversation_id": str(conversation_id),
            "reader_id": str(current_user.id),
            "last_read_at": read_time.isoformat(),
        },
    )
    return {"status": "ok", "last_read_at": read_time.isoformat()}