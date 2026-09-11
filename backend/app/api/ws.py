from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.repositories.user import UserRepository
from app.services.auth import AuthService
from app.services.connection_manager import connection_manager
from app.services.websocket_handler import WebSocketHandler

router = APIRouter()

CLOSE_UNAUTHORIZED = 4401


def get_websocket_handler(db: AsyncSession = Depends(get_db)) -> WebSocketHandler:
    return WebSocketHandler(db)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
    handler: WebSocketHandler = Depends(get_websocket_handler),
) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return

    try:
        user = await AuthService(UserRepository(db)).get_current_user(token)
    except AppException:
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return

    await websocket.accept()
    await connection_manager.connect(user.id, websocket)

    try:
        while True:
            try:
                raw = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except (ValueError, TypeError):
                raw = None
            try:
                await handler.handle_incoming_frame(websocket, user, raw)
            except WebSocketDisconnect:
                break
    finally:
        await connection_manager.disconnect(user.id, websocket)