import logging
import time

from app.clients.redis import get_binary_redis, get_redis
from app.schemas.telemetry import TelemetryPoint
from app.services.telemetry.pack import pack_points

logger = logging.getLogger(__name__)

_TTL_SECONDS = 3
_SEQUENCE = "telemetry:batch:seq"
_LATEST = "telemetry:live:batch"
_open_second = -1
_open_id: int | None = None


class BatchMissingError(Exception):
    """The batch id is not in Redis."""


def _points_key(batch_id: int) -> str:
    return f"telemetry:batch:{batch_id}:points"


async def publish_batch(points: list[TelemetryPoint]) -> int | None:
    """Pack points into the open second. The socket hears the id once that second closes."""
    global _open_id, _open_second
    if not points:
        return None
    body = pack_points(points)
    second = int(time.time())
    try:
        if _open_id is not None and second == _open_second:
            await append_to_existing_batch(_open_id, body)
            return _open_id
        if _open_id is not None:
            await finish_batch(_open_id)
        batch_id = int(await get_redis().incr(_SEQUENCE))
        await get_binary_redis().set(_points_key(batch_id), body, ex=_TTL_SECONDS)
    except Exception:
        logger.exception("failed to store telemetry batch of %s points", len(points))
        return None
    _open_second = second
    _open_id = batch_id
    logger.info("opened telemetry batch %s (%s bytes)", batch_id, len(body))
    return batch_id


async def append_to_existing_batch(batch_id: int, body: bytes) -> None:
    key = _points_key(batch_id)
    binary = get_binary_redis()
    await binary.append(key, body)
    await binary.expire(key, _TTL_SECONDS)
    logger.debug("appended telemetry batch %s (%s bytes)", batch_id, len(body))


async def finish_batch(batch_id: int) -> None:
    """Make a closed second visible. Later flushes in that second stay on this id."""
    await get_binary_redis().expire(_points_key(batch_id), _TTL_SECONDS)
    await get_redis().set(_LATEST, batch_id, ex=_TTL_SECONDS)
    logger.info("published telemetry batch %s", batch_id)


async def latest_batch_id() -> int | None:
    """Return the batch id the live socket should announce."""
    value = await get_redis().get(_LATEST)
    if value is None:
        return None
    return int(value)


async def batch_body(batch_id: int) -> bytes:
    """Return the packed batch stored for this id."""
    raw = await get_binary_redis().get(_points_key(batch_id))
    if not isinstance(raw, bytes):
        logger.info("telemetry batch %s is missing", batch_id)
        raise BatchMissingError(batch_id)
    return raw
