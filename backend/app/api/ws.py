import uuid
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.repositories.user import UserRepository
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
        payload = decode_token(token, token_type="access")
        if payload is None:
            await websocket.close(code=CLOSE_UNAUTHORIZED)
            return

        raw_id = payload.get("sub")
        user_id = uuid.UUID(str(raw_id))
        user = await UserRepository(db).get_by_id(user_id)
        if user is None or not user.is_active:
            await websocket.close(code=CLOSE_UNAUTHORIZED)
            return
    except Exception:
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return



    await websocket.accept()
    await connection_manager.connect(user.id, websocket)

    # Send initial snapshot of currently connected users
    online_uids = await connection_manager.get_online_user_ids()
    await websocket.send_json({
        "type": "presence_sync",
        "data": {"online_user_ids": [str(uid) for uid in online_uids]},
    })

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