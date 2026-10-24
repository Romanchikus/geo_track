import asyncio
import logging
from typing import Protocol

from redis.asyncio import Redis

from canary_tests.positions import DEFAULT_SPEED_KMH

logger = logging.getLogger(__name__)

SPEED_KEY = "load:speed_kmh"


class Pace(Protocol):
    async def read(self) -> tuple[float, int]:
        """Return speed in km/h and how many points to publish this second."""


class RedisPace:
    """Read canary speed from Redis, keeping the last good value."""

    def __init__(self, url: str, points_per_second: int, client: Redis | None = None) -> None:
        self._url = url
        self._client = client
        self._speed = DEFAULT_SPEED_KMH
        self._rate = points_per_second
        self._down = False
        self._lock = asyncio.Lock()

    async def read(self) -> tuple[float, int]:
        async with self._lock:
            speed = next_pace(await self._fetch(), self._speed)
            if speed != self._speed:
                logger.info("canary pace is %s km/h", speed)
                self._speed = speed
            return self._speed, self._rate

    async def close(self) -> None:
        client = self._client
        self._client = None
        if client is not None:
            await client.aclose()

    async def _fetch(self) -> object:
        try:
            client = self._client
            if client is None:
                client = Redis.from_url(
                    self._url,
                    decode_responses=True,
                    socket_timeout=1.0,
                    socket_connect_timeout=1.0,
                )
                self._client = client
            speed_raw = await client.get(SPEED_KEY)
        except Exception:
            if not self._down:
                logger.exception("failed to read canary pace from redis")
                self._down = True
            await self.close()
            return None
        if self._down:
            logger.info("canary pace redis is reachable again")
            self._down = False
        return speed_raw


def next_pace(speed_raw: object, speed_kmh: float) -> float:
    """Keep the previous speed when Redis has no usable value."""
    speed = _positive_float(speed_raw)
    return speed_kmh if speed is None else speed


def _positive_float(raw: object) -> float | None:
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if value <= 0 or value > 1_000_000:
        return None
    return value
