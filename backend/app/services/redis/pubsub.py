import asyncio
import json
import logging
import uuid
from typing import Any
from redis.asyncio import Redis

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

EVENTS_CHANNEL = "relay:events"


class RedisPubSubManager:
    """
    Handles publishing events to Redis and listening to incoming events
    across multiple server instances with auto-reconnection and clean shutdown.
    """
    def __init__(self, redis: Redis | None = None):
        self._redis = redis
        self._listener_task: asyncio.Task | None = None
        self._running = False
        self.instance_id = str(uuid.uuid4())


    def _get_client(self) -> Redis:
        return self._redis or get_redis_client()


    async def publish_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish a JSON payload to the global events channel."""
        client = self._get_client()
        message = {
            "type": event_type,
            "origin_instance": self.instance_id,
            "data": data,
        }
        await client.publish(EVENTS_CHANNEL, json.dumps(message))


    async def start_listener(self) -> None:
        """Start the background subscriber task with reconnect logic."""
        if self._running:
            return
        self._running = True
        self._listener_task = asyncio.create_task(self._listen_loop())
        logger.info("Redis Pub/Sub background listener started (instance=%s)", self.instance_id)


    async def stop_listener(self) -> None:
        """Gracefully stop and await the background subscriber task on shutdown."""
        self._running = False
        if self._listener_task:
            logger.info("Stopping Redis Pub/Sub listener...")
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None


    async def _listen_loop(self) -> None:
        backoff = 1
        while self._running:
            try:
                client = self._get_client()
                pubsub = client.pubsub()
                await pubsub.subscribe(EVENTS_CHANNEL)
                logger.info("Subscribed to Redis channel: %s", EVENTS_CHANNEL)
                backoff = 1  # Reset backoff on successful connection

                while self._running:
                    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if msg is None:
                        await asyncio.sleep(0.05)
                        continue

                    raw_data = msg.get("data")
                    if not raw_data:
                        continue

                    try:
                        payload = json.loads(raw_data)
                    except (ValueError, TypeError):
                        continue

                    await self._dispatch_event(payload)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self._running:
                    break
                logger.warning(
                    "Redis Pub/Sub connection error (%s). Reconnecting in %s seconds...",
                    e,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)


    async def _dispatch_event(self, payload: dict) -> None:
        """Forward incoming Pub/Sub events to local WebSockets via ConnectionManager."""
        from app.services.connection_manager import connection_manager

        event_type = payload.get("type")
        data = payload.get("data", {})
        origin_instance = payload.get("origin_instance")

        # 1. New Message
        if event_type == "message":
            conversation_id = uuid.UUID(data["conversation_id"])
            sender_id = uuid.UUID(data["sender_id"])
            # Distribute to local subscribers of this conversation
            await connection_manager.send_to_subscribers_local(
                conversation_id,
                {"type": "message", "data": data},
                exclude_user_id=sender_id,
            )

        # 2. Presence Change
        elif event_type == "presence":
            user_id = uuid.UUID(data["user_id"])
            status = data["status"]  # "online" or "offline"
            # Broadcast to all connected local clients
            await connection_manager.broadcast_presence(user_id, status)

        # 3. Typing Indicator
        elif event_type == "typing":
            conversation_id = uuid.UUID(data["conversation_id"])
            user_id = uuid.UUID(data["user_id"])
            is_typing = data["is_typing"]
            await connection_manager.send_to_subscribers_local(
                conversation_id,
                {
                    "type": "typing",
                    "data": {
                        "conversation_id": str(conversation_id),
                        "user_id": str(user_id),
                        "is_typing": is_typing,
                    },
                },
                exclude_user_id=user_id,
            )

        # 4. Read Receipt
        elif event_type == "read_receipt":
            conversation_id = uuid.UUID(data["conversation_id"])
            reader_id = uuid.UUID(data["reader_id"])
            last_read_at = data["last_read_at"]
            await connection_manager.send_to_subscribers_local(
                conversation_id,
                {
                    "type": "read_receipt",
                    "data": {
                        "conversation_id": str(conversation_id),
                        "reader_id": str(reader_id),
                        "last_read_at": last_read_at,
                    },
                },
                exclude_user_id=reader_id,
            )


pubsub_manager = RedisPubSubManager()
