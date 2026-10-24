import logging
import time

from app.clients.redis import get_redis

logger = logging.getLogger(__name__)

_PREFIX = "telemetry:stored:"
_TOTAL_KEY = "telemetry:stored:total"
_TTL_SECONDS = 3


async def record_stored(count: int, now: float | None = None) -> None:
    """Count rows inserted during this second, and add them to the running total."""
    if count <= 0:
        return
    second = int(time.time() if now is None else now)
    key = f"{_PREFIX}{second}"
    try:
        async with get_redis().pipeline(transaction=False) as pipe:
            pipe.incrby(key, count)
            pipe.expire(key, _TTL_SECONDS)
            pipe.incrby(_TOTAL_KEY, count)
            await pipe.execute()
    except Exception:
        logger.exception("failed to record stored telemetry rate")


async def stored_last_second(now: float | None = None) -> int:
    """Return how many telemetry rows were inserted during the previous second."""
    second = int(time.time() if now is None else now) - 1
    value = await get_redis().get(f"{_PREFIX}{second}")
    if value is None:
        return 0
    return int(value)


async def stored_total() -> int:
    """Return how many telemetry rows were inserted since the counter started."""
    value = await get_redis().get(_TOTAL_KEY)
    if value is None:
        return 0
    return int(value)
