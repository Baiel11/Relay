import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.user import UserBrief


class ConversationCreate(BaseModel):
    other_user_id: uuid.UUID


class ConversationResponse(BaseModel):
    id: uuid.UUID
    other_user: UserBrief
    created_at: datetime
    unread_count: int = 0
    is_online: bool = False


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    total: int