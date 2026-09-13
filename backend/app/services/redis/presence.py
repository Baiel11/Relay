import time
import uuid
from redis.asyncio import Redis

from app.core.redis import get_redis_client


class RedisPresenceService:
    def __init__(self, redis: Redis | None = None, heartbeat_ttl: int = 60):
        self._redis = redis
        self.heartbeat_ttl = heartbeat_ttl


    def _get_client(self) -> Redis:
        return self._redis or get_redis_client()


    def _presence_key(self, user_id: uuid.UUID) -> str:
        return f"presence:{user_id}"


    async def set_online(self, user_id: uuid.UUID) -> None:
        """Mark user online with heartbeat TTL."""
        client = self._get_client()
        await client.set(self._presence_key(user_id), str(int(time.time())), ex=self.heartbeat_ttl)


    async def refresh_heartbeat(self, user_id: uuid.UUID) -> None:
        """Extend presence TTL on WebSocket ping/pong frame."""
        await self.set_online(user_id)


    async def set_offline(self, user_id: uuid.UUID) -> None:
        """Explicitly remove presence key when last socket disconnects."""
        client = self._get_client()
        await client.delete(self._presence_key(user_id))


    async def is_online(self, user_id: uuid.UUID) -> bool:
        """Check if user has an active presence key."""
        client = self._get_client()
        exists = await client.exists(self._presence_key(user_id))
        return bool(exists)


    async def get_online_statuses(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, bool]:
        """Pipelined presence check for a list of users."""
        if not user_ids:
            return {}

        client = self._get_client()
        async with client.pipeline(transaction=False) as pipe:
            for uid in user_ids:
                pipe.exists(self._presence_key(uid))
            results = await pipe.execute()

        return {uid: bool(results[i]) for i, uid in enumerate(user_ids)}


presence_service = RedisPresenceService()
