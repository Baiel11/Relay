from starlette.websockets import WebSocket

from app.core.exceptions import AppException


def error_payload(code: str, detail: str) -> dict:
    return {"type": "error", "code": code, "detail": detail}


def app_exception_code(exc: AppException) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
    }.get(exc.status_code, "error")


async def send_error(websocket: WebSocket, code: str, detail: str) -> None:
    await websocket.send_json(error_payload(code, detail))