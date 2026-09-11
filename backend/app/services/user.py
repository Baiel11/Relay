from app.repositories import PagedResult
from app.repositories.user import UserRepository
from app.models.user import User


class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def search(self, query: str, limit: int = 20, offset: int = 0) -> PagedResult[User]:
        return await self.user_repo.search(query, limit=limit, offset=offset)
