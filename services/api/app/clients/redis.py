import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from app.core.config import settings
from app.schemas.telemetry import TelemetryPoint

logger = logging.getLogger(__name__)

TELEMETRY_CHANNEL = "telemetry.points"

_client: Redis | None = None
_binary: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def get_binary_redis() -> Redis:
    """Redis connection that keeps cached batch bodies as raw bytes."""
    global _binary
    if _binary is None:
        _binary = Redis.from_url(settings.redis_url, decode_responses=False)
    return _binary


async def close_redis() -> None:
    global _client, _binary
    client = _client
    binary = _binary
    _client = None
    _binary = None
    if client is not None:
        await client.aclose()
    if binary is not None:
        await binary.aclose()
    if client is not None or binary is not None:
        logger.info("redis disconnected")


async def publish_live(points: list[TelemetryPoint]) -> None:
    if not points:
        return
    redis = get_redis()
    try:
        async with redis.pipeline(transaction=False) as pipe:
            for point in points:
                pipe.publish(TELEMETRY_CHANNEL, point.model_dump_json())
            await pipe.execute()
    except Exception:
        logger.exception("failed to publish %s telemetry points", len(points))
        raise
    logger.debug("published %s telemetry points", len(points))


@asynccontextmanager
async def subscribe_live() -> AsyncIterator[PubSub]:
    pubsub = get_redis().pubsub()
    await pubsub.subscribe(TELEMETRY_CHANNEL)
    try:
        yield pubsub
    finally:
        await pubsub.unsubscribe(TELEMETRY_CHANNEL)
        await pubsub.aclose()
