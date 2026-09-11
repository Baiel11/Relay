import asyncio
import uuid

from starlette.websockets import WebSocket


class WebSocketConnectionManager:
    """In-process WebSocket hub.

    Tracks active connections per user plus per-connection conversation
    subscriptions, and delivers frames to subscribers of a conversation.
    Multi-instance delivery is out of scope here (Phase 6 adds Redis pub/sub).
    """


    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = {}
        self._websocket_user: dict[WebSocket, uuid.UUID] = {}
        self._subscriptions: dict[WebSocket, set[uuid.UUID]] = {}
        self._send_locks: dict[WebSocket, asyncio.Lock] = {}
        self._lock = asyncio.Lock()


    async def connect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.setdefault(user_id, set()).add(websocket)
            self._websocket_user[websocket] = user_id
            self._subscriptions.setdefault(websocket, set())
            self._send_locks.setdefault(websocket, asyncio.Lock())


    async def disconnect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(user_id)
            if sockets:
                sockets.discard(websocket)
                if not sockets:
                    self._connections.pop(user_id, None)
            self._websocket_user.pop(websocket, None)
            self._subscriptions.pop(websocket, None)
            self._send_locks.pop(websocket, None)


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


    async def send_to_subscribers(
        self,
        conversation_id: uuid.UUID,
        payload: dict,
        exclude_user_id: uuid.UUID | None = None,
    ) -> None:
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


    async def send_to_user_non_subscribed(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        payload: dict,
    ) -> None:
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


    def reset(self) -> None:
        """Clear all state. Used by tests between cases."""
        self._connections.clear()
        self._websocket_user.clear()
        self._subscriptions.clear()
        self._send_locks.clear()


connection_manager = WebSocketConnectionManager()