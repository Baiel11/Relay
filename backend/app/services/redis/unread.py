import uuid
from typing import Awaitable, Callable
from redis.asyncio import Redis

from app.core.redis import get_redis_client


class RedisUnreadService:
    def __init__(self, redis: Redis | None = None, cache_ttl: int = 86400):
        self._redis = redis
        self.cache_ttl = cache_ttl


    def _get_client(self) -> Redis:
        return self._redis or get_redis_client()


    def _unread_key(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> str:
        return f"unread:{user_id}:{conversation_id}"


    async def increment_unread(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> int:
        """Atomically increment unread counter in Redis when a new message arrives."""
        client = self._get_client()
        key = self._unread_key(user_id, conversation_id)
        async with client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, self.cache_ttl)
            res = await pipe.execute()
        return int(res[0])


    async def reset_unread(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
        """Clear unread counter when conversation is read."""
        client = self._get_client()
        key = self._unread_key(user_id, conversation_id)
        await client.set(key, 0, ex=self.cache_ttl)


    async def get_unread(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        db_fallback: Callable[[], Awaitable[int]] | None = None,
    ) -> int:
        """
        Get unread count from Redis cache.
        If cache miss (Redis evicted or restarted) and db_fallback provided,
        recompute from PostgreSQL, populate Redis cache, and return.
        """
        client = self._get_client()
        key = self._unread_key(user_id, conversation_id)
        cached = await client.get(key)
        if cached is not None:
            return int(cached)

        if db_fallback is not None:
            count = await db_fallback()
            await client.set(key, count, ex=self.cache_ttl)
            return count

        return 0


unread_service = RedisUnreadService()
