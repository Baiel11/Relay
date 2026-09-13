import asyncio
import logging
import uuid

from starlette.websockets import WebSocket

from app.services.redis.presence import presence_service
from app.services.redis.pubsub import pubsub_manager

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """
    WebSocket connection hub managing active user sessions, conversation subscriptions,
    multi-tab reference counting for presence, and Redis Pub/Sub event broadcasting.
    """

    def __init__(self) -> None:
        # user_id -> set of active WebSockets (multi-tab / multi-device support)
        self._connections: dict[uuid.UUID, set[WebSocket]] = {}
        self._websocket_user: dict[WebSocket, uuid.UUID] = {}
        self._subscriptions: dict[WebSocket, set[uuid.UUID]] = {}
        self._send_locks: dict[WebSocket, asyncio.Lock] = {}
        self._lock = asyncio.Lock()


    async def connect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        """Register connection and update presence only on FIRST socket for user."""
        is_first_connection = False
        async with self._lock:
            sockets = self._connections.setdefault(user_id, set())
            is_first_connection = (len(sockets) == 0)
            sockets.add(websocket)
            self._websocket_user[websocket] = user_id
            self._subscriptions.setdefault(websocket, set())
            self._send_locks.setdefault(websocket, asyncio.Lock())

        if is_first_connection:
            try:
                await presence_service.set_online(user_id)
                # Broadcast immediately to local clients
                await self.broadcast_presence(user_id, "online")
                # Publish presence change event across cluster
                await pubsub_manager.publish_event(
                    "presence", {"user_id": str(user_id), "status": "online"}
                )
            except Exception as e:
                logger.warning("Failed to publish online presence: %s", e)


    async def disconnect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        """Unregister connection and update presence only when LAST socket closes."""
        is_last_connection = False
        async with self._lock:
            sockets = self._connections.get(user_id)
            if sockets:
                sockets.discard(websocket)
                if not sockets:
                    self._connections.pop(user_id, None)
                    is_last_connection = True
            self._websocket_user.pop(websocket, None)
            self._subscriptions.pop(websocket, None)
            self._send_locks.pop(websocket, None)

        if is_last_connection:
            try:
                await presence_service.set_offline(user_id)
                # Broadcast immediately to local clients
                await self.broadcast_presence(user_id, "offline")
                # Publish presence change event across cluster
                await pubsub_manager.publish_event(
                    "presence", {"user_id": str(user_id), "status": "offline"}
                )
            except Exception as e:
                logger.warning("Failed to publish offline presence: %s", e)


    async def is_subscribed(self, websocket: WebSocket, conversation_id: uuid.UUID) -> bool:
        async with self._lock:
            subs = self._subscriptions.get(websocket)
            return subs is not None and conversation_id in subs


    async def set_subscribed(
        self,
        websocket: WebSocket,
        conversation_id: uuid.UUID,
        subscribed: bool = True,
    ) -> None:
        async with self._lock:
            subs = self._subscriptions.get(websocket)
            if subs is None:
                return
            if subscribed:
                subs.add(conversation_id)
            else:
                subs.discard(conversation_id)


    async def send_to_user(self, user_id: uuid.UUID, payload: dict) -> None:
        """Send a frame to all local tabs/devices belonging to user_id."""
        async with self._lock:
            targets = list(self._connections.get(user_id) or ())
        for websocket in targets:
            lock = self._send_locks.get(websocket)
            if lock is None:
                continue
            async with lock:
                try:
                    await websocket.send_json(payload)
                except Exception:
                    continue


    async def send_to_subscribers_local(
        self,
        conversation_id: uuid.UUID,
        payload: dict,
        exclude_user_id: uuid.UUID | None = None,
    ) -> None:
        """Deliver frame to all locally connected sockets subscribed to the conversation."""
        async with self._lock:
            targets = [
                websocket
                for websocket, subs in self._subscriptions.items()
                if conversation_id in subs
                and self._websocket_user.get(websocket) != exclude_user_id
            ]
        for websocket in targets:
            lock = self._send_locks.get(websocket)
            if lock is None:
                continue
            async with lock:
                try:
                    await websocket.send_json(payload)
                except Exception:
                    continue


    async def send_to_subscribers(
        self,
        conversation_id: uuid.UUID,
        payload: dict,
        exclude_user_id: uuid.UUID | None = None,
    ) -> None:
        """Publish event via Redis Pub/Sub to reach subscribers across all instances."""
        # 1. Deliver to local subscribers immediately
        await self.send_to_subscribers_local(conversation_id, payload, exclude_user_id)
        # 2. Publish to Redis for other cluster instances
        await pubsub_manager.publish_event(
            payload.get("type", "message"),
            payload.get("data", {}),
        )


    async def send_to_user_non_subscribed(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        payload: dict,
    ) -> None:
        """Send notification frame to user if they are online but not actively in the chat."""
        async with self._lock:
            targets = [
                websocket
                for websocket in self._connections.get(user_id, ())
                if conversation_id not in self._subscriptions.get(websocket, ())
            ]
        for websocket in targets:
            lock = self._send_locks.get(websocket)
            if lock is None:
                continue
            async with lock:
                try:
                    await websocket.send_json(payload)
                except Exception:
                    continue


    async def broadcast_presence(self, user_id: uuid.UUID, status: str) -> None:
        """Broadcast presence event to all connected local clients."""
        payload = {
            "type": "presence",
            "data": {"user_id": str(user_id), "status": status},
        }
        async with self._lock:
            all_sockets = list(self._websocket_user.keys())
        for ws in all_sockets:
            lock = self._send_locks.get(ws)
            if lock is None:
                continue
            async with lock:
                try:
                    await ws.send_json(payload)
                except Exception:
                    continue


    async def close_user_connections(self, user_id: uuid.UUID) -> None:
        """Explicitly close all open websockets for a user (e.g. on logout)."""
        async with self._lock:
            sockets = list(self._connections.get(user_id, ()))
        for ws in sockets:
            try:
                await ws.close(code=1000)
            except Exception:
                pass


    async def get_online_user_ids(self) -> set[uuid.UUID]:
        """Return set of user IDs with active connections."""
        async with self._lock:
            return set(self._connections.keys())


    def reset(self) -> None:
        """Clear all in-memory connections."""
        self._connections.clear()
        self._websocket_user.clear()
        self._subscriptions.clear()
        self._send_locks.clear()


connection_manager = WebSocketConnectionManager()