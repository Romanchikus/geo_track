import logging
from typing import cast

from redis.exceptions import RedisError

from app.clients.redis import get_redis
from app.core.config import settings
from app.schemas.load import LoadControl, LoadUpdate

logger = logging.getLogger(__name__)

SPEED_KEY = "load:speed_kmh"
BATCH_SIZE_KEY = "load:telemetry_batch_max_size"
_MAX_BATCH = 10_000

_reported_batch: int | None = None
_batch_down = False
_bad_batch: str | None = None


async def read_load() -> LoadControl:
    """Return the load values stored for the canary and the batch writers."""
    try:
        raw = await get_redis().mget(SPEED_KEY, BATCH_SIZE_KEY)
    except RedisError:
        logger.exception("failed to read load control")
        raise
    speed_raw, batch_raw = raw
    return LoadControl(
        speed_kmh=_speed(speed_raw),
        telemetry_batch_max_size=_batch_size(batch_raw),
    )


async def update_load(body: LoadUpdate) -> LoadControl:
    """Store the fields that were sent. Missing fields keep their previous value."""
    redis = get_redis()
    try:
        if body.speed_kmh is not None:
            await redis.set(SPEED_KEY, str(body.speed_kmh))
        if body.telemetry_batch_max_size is not None:
            await redis.set(BATCH_SIZE_KEY, str(body.telemetry_batch_max_size))
    except RedisError:
        logger.exception("failed to store load control")
        raise
    logger.info(
        "load control set speed_kmh=%s telemetry_batch_max_size=%s",
        body.speed_kmh,
        body.telemetry_batch_max_size,
    )
    return await read_load()


async def batch_max_size() -> int:
    """How many telemetry points one batch may hold before it flushes."""
    global _batch_down
    try:
        raw = await get_redis().get(BATCH_SIZE_KEY)
    except RedisError:
        if not _batch_down:
            logger.exception("failed to read telemetry batch max size")
            _batch_down = True
        return _remember_batch(settings.telemetry_batch_max_size)
    if _batch_down:
        logger.info("telemetry batch max size is readable again")
        _batch_down = False
    parsed = _batch_size(raw)
    count = settings.telemetry_batch_max_size if parsed is None else parsed
    return _remember_batch(count)


def _remember_batch(count: int) -> int:
    global _reported_batch
    if count != _reported_batch:
        logger.info("telemetry batch max size is %s", count)
        _reported_batch = count
    return count


def _speed(raw: object) -> float | None:
    if raw is None:
        return None
    try:
        value = float(cast(str, raw))
    except (TypeError, ValueError):
        logger.warning("ignoring load speed %s", raw)
        return None
    if value <= 0 or value > 1_000_000:
        logger.warning("ignoring load speed %s", raw)
        return None
    return value


def _batch_size(raw: object) -> int | None:
    global _bad_batch
    if raw is None:
        return None
    text = str(raw)
    try:
        value = int(text)
    except ValueError:
        value = 0
    if value < 1 or value > _MAX_BATCH:
        if text != _bad_batch:
            logger.warning("ignoring telemetry batch max size %s", text)
            _bad_batch = text
        return None
    _bad_batch = None
    return value
