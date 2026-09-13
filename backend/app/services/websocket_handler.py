import logging
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.core.exceptions import AppException
from app.models.user import User
from app.repositories.conversation import ConversationRepository
from app.repositories.conversation_read import ConversationReadRepository
from app.repositories.message import MessageRepository
from app.repositories.user import UserRepository
from app.schemas.message import MessageResponse
from app.schemas.ws import (
    WSMarkRead,
    WSMessageSend,
    WSPing,
    WSSubscribe,
    WSSync,
    WSTyping,
)
from app.services.connection_manager import connection_manager
from app.services.conversation import ConversationService
from app.services.message import MessageService
from app.services.redis.presence import presence_service
from app.services.redis.pubsub import pubsub_manager
from app.services.redis.rate_limiter import rate_limiter
from app.services.redis.typing import typing_service
from app.services.redis.unread import unread_service
from app.utils.ws_utils import app_exception_code, send_error

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """WebSocket protocol: frame validation, dispatch, rate-limiting, and business flows."""

    FRAME_MODELS: dict[str, type[BaseModel]] = {
        "ping": WSPing,
        "send_message": WSMessageSend,
        "subscribe": WSSubscribe,
        "sync": WSSync,
        "typing": WSTyping,
        "mark_read": WSMarkRead,
    }


    def __init__(self, db: AsyncSession):
        self.db = db
        user_repo = UserRepository(db)
        self.conversation_service = ConversationService(
            ConversationRepository(db), user_repo
        )
        self.message_service = MessageService(MessageRepository(db))
        self.read_repo = ConversationReadRepository(db)

        self._handlers = {
            "ping": self.handle_ping,
            "send_message": self.handle_send_message,
            "subscribe": self.handle_subscribe,
            "sync": self.handle_sync,
            "typing": self.handle_typing,
            "mark_read": self.handle_mark_read,
        }


    async def handle_incoming_frame(
        self,
        websocket: WebSocket,
        user: User,
        raw: dict | None,
    ) -> None:
        if raw is None:
            await send_error(websocket, "invalid_json", "Frame is not valid JSON")
            return

        if not isinstance(raw, dict):
            await send_error(websocket, "invalid_frame", "Frame must be a JSON object")
            return

        frame_type = raw.get("type")
        model_cls = self.FRAME_MODELS.get(frame_type)
        if model_cls is None:
            await send_error(
                websocket, "unknown_type", f"Unknown frame type: {frame_type!r}"
            )
            return

        try:
            frame = model_cls.model_validate(raw)
        except ValidationError:
            await send_error(websocket, "invalid_frame", "Frame payload is invalid")
            return

        try:
            await self._handlers[frame_type](websocket, user, frame)
        except WebSocketDisconnect:
            raise
        except AppException as exc:
            await send_error(websocket, app_exception_code(exc), exc.detail)
        except Exception:
            logger.exception("Unhandled websocket error")
            await send_error(websocket, "internal_error", "Internal server error")


    async def handle_ping(
        self, websocket: WebSocket, user: User, frame: WSPing
    ) -> None:
        # Refresh presence heartbeat in Redis
        await presence_service.refresh_heartbeat(user.id)
        await websocket.send_json({"type": "pong"})

    async def handle_send_message(
        self, websocket: WebSocket, user: User, frame: WSMessageSend
    ) -> None:
        # 1. Enforce atomic Lua sliding-window rate limit on send_message
        allowed = await rate_limiter.check_ws_send_message(user.id, limit=30, window=60)
        if not allowed:
            await send_error(
                websocket,
                "rate_limited",
                "You are sending messages too fast. Please wait a moment.",
            )
            return

        # 2. Scoping authorization
        conversation = await self.conversation_service.get_for_user(
            frame.conversation_id, user.id
        )

        # 3. Persist to PostgreSQL (Source of Truth)
        message, created = await self.message_service.send_message(
            frame.conversation_id,
            user.id,
            frame.content,
            frame.client_message_id,
        )
        payload = MessageResponse.model_validate(message).model_dump(mode="json")

        # 4. ACK to sender
        await connection_manager.send_to_user(
            user.id,
            {"type": "ack", "data": {"message": payload, "created": created}},
        )

        if created:
            # 5. Broadcast to conversation subscribers via Pub/Sub
            await connection_manager.send_to_subscribers(
                frame.conversation_id,
                {"type": "message", "data": payload},
                exclude_user_id=user.id,
            )

            recipient_id = (
                conversation.participant_b
                if conversation.participant_a == user.id
                else conversation.participant_a
            )

            # 6. Atomic increment in Redis unread counter
            unread_count = await unread_service.increment_unread(
                recipient_id, frame.conversation_id
            )

            # 7. Notify recipient (unread badge notification)
            await connection_manager.send_to_user(
                recipient_id,
                {
                    "type": "unread_update",
                    "data": {
                        "conversation_id": str(frame.conversation_id),
                        "unread_count": unread_count,
                    },
                },
            )

            # 8. If recipient not in active chat, deliver full message so preview & chat update
            await connection_manager.send_to_user_non_subscribed(
                recipient_id,
                frame.conversation_id,
                {"type": "message", "data": payload},
            )


    async def handle_subscribe(
        self, websocket: WebSocket, user: User, frame: WSSubscribe
    ) -> None:
        conversation = await self.conversation_service.get_for_user(
            frame.conversation_id, user.id
        )
        await connection_manager.set_subscribed(
            websocket, frame.conversation_id, frame.subscribed
        )

        # Also get partner online presence
        other_id = (
            conversation.participant_b
            if conversation.participant_a == user.id
            else conversation.participant_a
        )
        partner_online = await presence_service.is_online(other_id)

        await websocket.send_json(
            {
                "type": "subscribed",
                "conversation_id": str(frame.conversation_id),
                "subscribed": frame.subscribed,
                "partner_online": partner_online,
            }
        )


    async def handle_sync(
        self, websocket: WebSocket, user: User, frame: WSSync
    ) -> None:
        await self.conversation_service.get_for_user(frame.conversation_id, user.id)
        result = await self.message_service.backfill(
            frame.conversation_id, frame.after_message_id, frame.limit
        )
        await connection_manager.set_subscribed(
            websocket, frame.conversation_id, True
        )
        await websocket.send_json(
            {"type": "messages", "data": result.model_dump(mode="json")}
        )


    async def handle_typing(
        self, websocket: WebSocket, user: User, frame: WSTyping
    ) -> None:
        conversation = await self.conversation_service.get_for_user(
            frame.conversation_id, user.id
        )
        # Update Redis typing key with 4s safety fallback
        await typing_service.set_typing(
            frame.conversation_id, user.id, frame.is_typing
        )

        payload = {
            "conversation_id": str(frame.conversation_id),
            "user_id": str(user.id),
            "is_typing": frame.is_typing,
        }

        # 1. Broadcast typing status across cluster via Pub/Sub
        await pubsub_manager.publish_event("typing", payload)

        # 2. Immediately deliver to local conversation subscribers
        await connection_manager.send_to_subscribers_local(
            frame.conversation_id,
            {"type": "typing", "data": payload},
            exclude_user_id=user.id,
        )

        # 3. Deliver directly to other conversation participant in case their socket is pending subscribe
        other_id = (
            conversation.participant_b
            if conversation.participant_a == user.id
            else conversation.participant_a
        )
        await connection_manager.send_to_user_non_subscribed(
            other_id,
            frame.conversation_id,
            {"type": "typing", "data": payload},
        )


    async def handle_mark_read(
        self, websocket: WebSocket, user: User, frame: WSMarkRead
    ) -> None:
        await self.conversation_service.get_for_user(
            frame.conversation_id, user.id
        )
        read_time = datetime.now(timezone.utc)

        # 1. Update PostgreSQL source of truth
        await self.read_repo.upsert_last_read(
            user.id, frame.conversation_id, read_time
        )

        # 2. Reset Redis unread cache
        await unread_service.reset_unread(user.id, frame.conversation_id)

        # 3. Publish read_receipt event via Pub/Sub so sender sees double tick ✓✓
        await pubsub_manager.publish_event(
            "read_receipt",
            {
                "conversation_id": str(frame.conversation_id),
                "reader_id": str(user.id),
                "last_read_at": read_time.isoformat(),
            },
        )