import uuid
from typing import Literal

from pydantic import BaseModel, Field


class WSPing(BaseModel):
    type: Literal["ping"]


class WSMessageSend(BaseModel):
    type: Literal["send_message"]
    conversation_id: uuid.UUID
    content: str = Field(min_length=1, max_length=4000)
    client_message_id: uuid.UUID | None = None


class WSSubscribe(BaseModel):
    type: Literal["subscribe"]
    conversation_id: uuid.UUID
    subscribed: bool = True


class WSSync(BaseModel):
    type: Literal["sync"]
    conversation_id: uuid.UUID
    after_message_id: uuid.UUID | None = None
    limit: int = Field(default=50, ge=1, le=200)