import time
import uuid
from typing import Any, Callable, cast
from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from app.core.redis import get_redis_client

# Atomic Lua script for sliding window rate limiter:
# KEYS[1] = rate limit key
# ARGV[1] = current timestamp (float / integer seconds or millis)
# ARGV[2] = window size in seconds
# ARGV[3] = max allowed requests in window
SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

local clear_before = now - window
redis.call('ZREMRANGEBYSCORE', key, '-inf', clear_before)
local current_requests = redis.call('ZCARD', key)

if current_requests < limit then
    redis.call('ZADD', key, now, now)
    redis.call('EXPIRE', key, math.ceil(window))
    return 1
else
    return 0
end
"""


class RedisRateLimiter:
    def __init__(self, redis: Redis | None = None):
        self._redis = redis


    def _get_client(self) -> Redis:
        return self._redis or get_redis_client()


    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> bool:
        """
        Executes atomic sliding-window check in Redis.
        Returns True if allowed, False if exceeded.
        """
        client = self._get_client()
        now = time.time()
        result = await cast(
            Any,
            client.eval(
                SLIDING_WINDOW_LUA,
                1,
                key,
                str(now),
                str(window_seconds),
                str(limit),
            ),
        )
        return bool(result == 1)


    async def check_ws_send_message(self, user_id: uuid.UUID, limit: int = 30, window: int = 60) -> bool:
        """Anti-spam check for WebSocket send_message frame (default: 30 msg/min)."""
        key = f"rl:ws:msg:{user_id}"
        return await self.check_rate_limit(key, limit, window)


rate_limiter = RedisRateLimiter()


def rate_limit(
    limit: int,
    window_seconds: int,
    key_func: Callable[[Request], str] | None = None,
):
    """
    FastAPI dependency for endpoint-level rate limiting.
    Defaults to client IP if key_func is not provided.
    """
    async def dependency(request: Request):
        if key_func:
            identifier = key_func(request)
        else:
            client_host = request.client.host if request.client else "unknown"
            identifier = client_host

        endpoint = request.url.path
        key = f"rl:http:{endpoint}:{identifier}"

        allowed = await rate_limiter.check_rate_limit(key, limit, window_seconds)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down and try again later.",
            )

    return dependency
