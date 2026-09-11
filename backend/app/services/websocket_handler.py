import logging

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.core.exceptions import AppException
from app.utils.ws_utils import app_exception_code, send_error
from app.models.user import User
from app.repositories.conversation import ConversationRepository
from app.repositories.message import MessageRepository
from app.repositories.user import UserRepository
from app.schemas.message import MessageResponse
from app.schemas.ws import WSPing, WSMessageSend, WSSubscribe, WSSync
from app.services.connection_manager import connection_manager
from app.services.conversation import ConversationService
from app.services.message import MessageService

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """WebSocket protocol: frame validation, dispatch, and business flows.

    The router is a thin transport layer — it only forwards raw JSON frames
    (or ``None`` when the frame could not be parsed) to handle_incoming_frame.
    """

    FRAME_MODELS: dict[str, type[BaseModel]] = {
        "ping": WSPing,
        "send_message": WSMessageSend,
        "subscribe": WSSubscribe,
        "sync": WSSync,
    }


    def __init__(self, db: AsyncSession):
        self.db = db
        user_repo = UserRepository(db)
        self.conversation_service = ConversationService(
            ConversationRepository(db), user_repo
        )
        self.message_service = MessageService(MessageRepository(db))
        self._handlers = {
            "ping": self.handle_ping,
            "send_message": self.handle_send_message,
            "subscribe": self.handle_subscribe,
            "sync": self.handle_sync,
        }


    async def handle_incoming_frame(
        self,
        websocket: WebSocket,
        user: User,
        raw: dict | None,
    ) -> None:
        if raw is None:
            await send_error(
                websocket, "invalid_json", "Frame is not valid JSON"
            )
            return

        if not isinstance(raw, dict):
            await send_error(
                websocket, "invalid_frame", "Frame must be a JSON object"
            )
            return

        frame_type = raw.get("type")
        model_cls = self.FRAME_MODELS.get(frame_type)
        if model_cls is None:
            await send_error(
                websocket,
                "unknown_type",
                f"Unknown frame type: {frame_type!r}",
            )
            return

        try:
            frame = model_cls.model_validate(raw)
        except ValidationError:
            await send_error(
                websocket, "invalid_frame", "Frame payload is invalid"
            )
            return

        try:
            await self._handlers[frame_type](websocket, user, frame)
        except WebSocketDisconnect:
            raise
        except AppException as exc:
            await send_error(
                websocket, app_exception_code(exc), exc.detail
            )
        except Exception:
            logger.exception("Unhandled websocket error")
            await send_error(
                websocket, "internal_error", "Internal server error"
            )


    async def handle_ping(
        self, websocket: WebSocket, user: User, frame: WSPing
    ) -> None:
        await websocket.send_json({"type": "pong"})


    async def handle_send_message(
        self, websocket: WebSocket, user: User, frame: WSMessageSend
    ) -> None:
        conversation = await self.conversation_service.get_for_user(
            frame.conversation_id, user.id
        )
        message, created = await self.message_service.send_message(
            frame.conversation_id,
            user.id,
            frame.content,
            frame.client_message_id,
        )
        payload = MessageResponse.model_validate(message).model_dump(mode="json")


        await connection_manager.send_to_user(
            user.id,
            {"type": "ack", "data": {"message": payload, "created": created}},
        )
        if created:
            await connection_manager.send_to_subscribers(
                frame.conversation_id,
                {"type": "message", "data": payload},
                exclude_user_id=user.id,
            )
            other_id = (
                conversation.participant_b
                if conversation.participant_a == user.id
                else conversation.participant_a
            )
            await connection_manager.send_to_user_non_subscribed(
                other_id,
                frame.conversation_id,
                {
                    "type": "new_message",
                    "data": {
                        "conversation_id": str(frame.conversation_id),
                        "message_id": payload["id"],
                        "sender_id": payload["sender_id"],
                        "preview": payload["content"][:100],
                        "created_at": payload["created_at"],
                    },
                },
            )


    async def handle_subscribe(
        self, websocket: WebSocket, user: User, frame: WSSubscribe
    ) -> None:
        await self.conversation_service.get_for_user(
            frame.conversation_id, user.id
        )
        await connection_manager.set_subscribed(
            websocket, frame.conversation_id, frame.subscribed
        )
        await websocket.send_json(
            {
                "type": "subscribed",
                "conversation_id": str(frame.conversation_id),
                "subscribed": frame.subscribed,
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