import asyncio
import contextlib
import logging
import time

from app.clients.redis import get_redis

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 3
_PREFIX = "http:requests:"
_FLUSH_SECONDS = 0.2
_pending = 0
_task: asyncio.Task[None] | None = None


class SecondTotal:
    """Sum counts and return the total after one second of elapsed steps."""

    def __init__(self) -> None:
        self._count = 0
        self._elapsed = 0.0

    def add(self, count: int, step: float) -> int | None:
        self._count += count
        self._elapsed += step
        if self._elapsed < 1:
            return None
        total = self._count
        self._count = 0
        self._elapsed = 0.0
        return total


_second = SecondTotal()


def note_request() -> None:
    """Count one request in memory. A background task writes the total to Redis."""
    global _pending
    _pending += 1


async def record_requests(count: int, now: float | None = None) -> None:
    """Add requests to the current second. The bucket expires after the 3 second window."""
    if count <= 0:
        return
    second = int(time.time() if now is None else now)
    key = f"{_PREFIX}{second}"
    redis = get_redis()
    async with redis.pipeline(transaction=False) as pipe:
        pipe.incrby(key, count)
        pipe.expire(key, WINDOW_SECONDS)
        await pipe.execute()


async def _flush_loop() -> None:
    global _pending
    last = time.monotonic()
    while True:
        await asyncio.sleep(_FLUSH_SECONDS)
        now = time.monotonic()
        step = now - last
        last = now
        count = _pending
        _pending = 0
        total = _second.add(count, step)
        if total:
            logger.info("fastapi requests %s", total)
        if count == 0:
            continue
        try:
            await record_requests(count)
        except Exception:
            _pending += count
            logger.exception("failed to record request rate")


def start_request_counter() -> None:
    global _task
    if _task is None:
        _task = asyncio.create_task(_flush_loop())


async def stop_request_counter() -> None:
    global _pending, _task
    task = _task
    _task = None
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    count = _pending
    _pending = 0
    if count:
        await record_requests(count)


async def requests_last_second(now: float | None = None) -> int:
    """Return how many requests arrived during the previous second."""
    second = int(time.time() if now is None else now) - 1
    value = await get_redis().get(f"{_PREFIX}{second}")
    if value is None:
        return 0
    return int(value)
