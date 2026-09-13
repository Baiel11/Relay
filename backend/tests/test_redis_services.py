import asyncio
import time
import uuid
import pytest
from fakeredis.aioredis import FakeRedis

from app.services.redis.rate_limiter import RedisRateLimiter
from app.services.redis.presence import RedisPresenceService
from app.services.redis.typing import RedisTypingService
from app.services.redis.unread import RedisUnreadService


@pytest.mark.asyncio
async def test_rate_limiter_sliding_window():
    fake = FakeRedis(decode_responses=True)
    limiter = RedisRateLimiter(fake)

    key = "test:rl:key"
    limit = 3
    window = 2  # 2 seconds window

    # 3 allowed
    assert await limiter.check_rate_limit(key, limit, window) is True
    assert await limiter.check_rate_limit(key, limit, window) is True
    assert await limiter.check_rate_limit(key, limit, window) is True

    # 4th rejected
    assert await limiter.check_rate_limit(key, limit, window) is False

    # Wait for window to clear
    await asyncio.sleep(2.1)
    assert await limiter.check_rate_limit(key, limit, window) is True


@pytest.mark.asyncio
async def test_presence_service():
    fake = FakeRedis(decode_responses=True)
    presence = RedisPresenceService(fake, heartbeat_ttl=2)

    user1 = uuid.uuid4()
    user2 = uuid.uuid4()

    assert await presence.is_online(user1) is False

    await presence.set_online(user1)
    assert await presence.is_online(user1) is True

    statuses = await presence.get_online_statuses([user1, user2])
    assert statuses[user1] is True
    assert statuses[user2] is False

    await presence.set_offline(user1)
    assert await presence.is_online(user1) is False


@pytest.mark.asyncio
async def test_typing_service_explicit_and_fallback():
    fake = FakeRedis(decode_responses=True)
    typing = RedisTypingService(fake, fallback_ttl=1)

    conv_id = uuid.uuid4()
    user_id = uuid.uuid4()

    assert await typing.is_typing(conv_id, user_id) is False

    # Start typing
    await typing.set_typing(conv_id, user_id, is_typing=True)
    assert await typing.is_typing(conv_id, user_id) is True

    # Explicit stop
    await typing.set_typing(conv_id, user_id, is_typing=False)
    assert await typing.is_typing(conv_id, user_id) is False

    # Fallback TTL expiration
    await typing.set_typing(conv_id, user_id, is_typing=True)
    await asyncio.sleep(1.1)
    assert await typing.is_typing(conv_id, user_id) is False


@pytest.mark.asyncio
async def test_unread_service_cache_and_db_fallback():
    fake = FakeRedis(decode_responses=True)
    unread = RedisUnreadService(fake)

    user_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    # DB fallback called on cache miss
    db_called = 0
    async def mock_db_count():
        nonlocal db_called
        db_called += 1
        return 7

    count = await unread.get_unread(user_id, conv_id, db_fallback=mock_db_count)
    assert count == 7
    assert db_called == 1

    # Second read served directly from Redis cache without calling DB
    cached = await unread.get_unread(user_id, conv_id, db_fallback=mock_db_count)
    assert cached == 7
    assert db_called == 1

    # Increment in Redis
    new_val = await unread.increment_unread(user_id, conv_id)
    assert new_val == 8

    # Reset
    await unread.reset_unread(user_id, conv_id)
    assert await unread.get_unread(user_id, conv_id) == 0
