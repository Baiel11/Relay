from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserBrief, UserSearchResponse
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(UserRepository(db))


@router.get("/search", response_model=UserSearchResponse)
async def search_users(
    q: str = Query(min_length=1, max_length=50),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    search_result = await user_service.search(q, limit=limit, offset=offset)
    return UserSearchResponse(
        results=[UserBrief.model_validate(u) for u in search_result.items],
        total=search_result.total,
        limit=limit,
        offset=offset,
    )
