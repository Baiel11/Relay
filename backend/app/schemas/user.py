import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserBrief(BaseModel):
    id: uuid.UUID
    username: str

    model_config = {"from_attributes": True}


class UserSearchResponse(BaseModel):
    results: list[UserBrief]
    total: int
    limit: int
    offset: int