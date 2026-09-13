import uuid
from redis.asyncio import Redis

from app.core.redis import get_redis_client


class RedisTypingService:
    def __init__(self, redis: Redis | None = None, fallback_ttl: int = 4):
        self._redis = redis
        self.fallback_ttl = fallback_ttl


    def _get_client(self) -> Redis:
        return self._redis or get_redis_client()


    def _typing_key(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> str:
        return f"typing:{conversation_id}:{user_id}"


    async def set_typing(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID, is_typing: bool
    ) -> None:
        """
        Record typing status.
        If is_typing is True, sets key with 4s safety fallback TTL.
        If is_typing is False (explicit stop), immediately deletes key.
        """
        client = self._get_client()
        key = self._typing_key(conversation_id, user_id)
        if is_typing:
            await client.set(key, "1", ex=self.fallback_ttl)
        else:
            await client.delete(key)


    async def is_typing(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        client = self._get_client()
        return bool(await client.exists(self._typing_key(conversation_id, user_id)))


typing_service = RedisTypingService()
