import logging
from urllib.parse import urlparse

from rstream import (
    Consumer,
    ConsumerOffsetSpecification,
    EventContext,
    OffsetNotFound,
    OffsetSpecification,
    OffsetType,
)
from wire.telemetry_codec import STREAM

from app.core.config import settings

logger = logging.getLogger(__name__)

SUBSCRIBER = "telemetry-worker"
SUBSCRIPTION = {"single-active-consumer": "true", "name": SUBSCRIBER}


def connect() -> Consumer:
    host, username, password = _address(settings.rabbitmq_url)
    logger.info("telemetry stream connecting to %s:%s", host, settings.rabbitmq_stream_port)
    return Consumer(
        host=host,
        port=settings.rabbitmq_stream_port,
        username=username,
        password=password,
        vhost="/",
    )


async def resume_from(consumer: Consumer) -> ConsumerOffsetSpecification:
    offset_type, offset = await _committed_offset(consumer)
    if offset_type is OffsetType.NEXT:
        return ConsumerOffsetSpecification(OffsetType.NEXT)
    return ConsumerOffsetSpecification(offset_type, offset)


async def on_active(active: bool, context: EventContext) -> OffsetSpecification:
    """Answer RabbitMQ when it makes this consumer active or standby."""
    if not active:
        logger.info("telemetry consumer is standby")
        return OffsetSpecification(OffsetType.NEXT, 0)
    logger.info("telemetry consumer is active")
    offset_type, offset = await _committed_offset(context.consumer)
    return OffsetSpecification(offset_type, offset)


async def _committed_offset(consumer: Consumer) -> tuple[OffsetType, int]:
    try:
        stored = await consumer.query_offset(STREAM, SUBSCRIBER)
    except OffsetNotFound:
        logger.info("telemetry stream has no stored offset")
        return OffsetType.NEXT, 0
    logger.info("telemetry stream resumes after offset %s", stored)
    return OffsetType.OFFSET, stored + 1


def _address(url: str) -> tuple[str, str, str]:
    parsed = urlparse(url)
    if parsed.hostname is None or parsed.username is None or parsed.password is None:
        logger.error("RABBITMQ_URL must include a host, username, and password")
        raise SystemExit(1)
    return parsed.hostname, parsed.username, parsed.password
