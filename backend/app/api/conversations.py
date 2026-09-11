from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.repositories.conversation import ConversationRepository
from app.repositories.user import UserRepository
from app.schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
)
from app.services.conversation import ConversationService


router = APIRouter(prefix="/conversations", tags=["conversations"])


def get_conversation_service(db: AsyncSession = Depends(get_db)) -> ConversationService:
    return ConversationService(ConversationRepository(db), UserRepository(db))


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