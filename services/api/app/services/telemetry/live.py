import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.services.telemetry.batches import latest_batch_id
from app.services.telemetry.rate import stored_last_second, stored_total

logger = logging.getLogger(__name__)


async def stream_telemetry(
    websocket: WebSocket,
    send_lock: asyncio.Lock | None = None,
    on_open: Callable[[], Awaitable[None]] | None = None,
) -> None:
    """Push stored-telemetry rates once a second."""
    await websocket.accept()
    if user_id_from_websocket(websocket) is None:
        logger.info("rejected telemetry stream; not authenticated")
        await websocket.close(code=4401)
        return
    logger.info("telemetry stream opened")
    try:
        if on_open is not None:
            await on_open()
        while True:
            now = time.time()
            stored = await stored_last_second(now)
            total = await stored_total()
            payload: dict[str, object] = {
                "stored": stored,
                "stored_total": total,
                "batch": await latest_batch_id(),
            }
            await _send_json(websocket, payload, send_lock)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info("telemetry stream closed")
    except Exception:
        logger.exception("telemetry stream failed")
        await websocket.close(code=1011)


async def _send_json(websocket: WebSocket, payload: dict[str, object], send_lock: asyncio.Lock | None) -> None:
    if send_lock is None:
        await websocket.send_json(payload)
        return
    async with send_lock:
        await websocket.send_json(payload)


def user_id_from_websocket(websocket: WebSocket) -> int | None:
    session = websocket.scope.get("session")
    if not isinstance(session, dict):
        return None
    user_id = session.get("user_id")
    if isinstance(user_id, int) and not isinstance(user_id, bool):
        return user_id
    return None
