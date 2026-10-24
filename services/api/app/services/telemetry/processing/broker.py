import asyncio
import contextlib
import logging
import time

from rstream import AMQPMessage, MessageContext, amqp_decoder
from wire.telemetry_codec import STREAM, decode

from app.clients.redis import close_redis
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine
from app.schemas.telemetry import TelemetryPoint
from app.services.load import batch_max_size
from app.services.telemetry.batches import publish_batch
from app.services.telemetry.processing.batch import Pending, TelemetryBatch
from app.services.telemetry.processing.save import save_telemetry_batch
from app.services.telemetry.processing.stream import SUBSCRIBER, SUBSCRIPTION, connect, on_active, resume_from
from app.services.telemetry.rate import record_stored

logger = logging.getLogger(__name__)

_received = 0
_report_task: asyncio.Task[None] | None = None


def point_from_payload(payload: bytes) -> TelemetryPoint:
    item = decode(payload)
    return TelemetryPoint(
        device_id=item.device_id,
        latitude=item.latitude,
        longitude=item.longitude,
        timestamp=item.timestamp,
    )


def message_body(body: object) -> bytes:
    if isinstance(body, (bytes, bytearray, memoryview)):
        return bytes(body)
    if isinstance(body, list):
        parts: list[bytes] = []
        for part in body:
            if not isinstance(part, (bytes, bytearray, memoryview)):
                raise ValueError("telemetry payload was not bytes")
            parts.append(bytes(part))
        if parts:
            return b"".join(parts)
    raise ValueError("telemetry payload was not bytes")


async def count_batch(items: list[Pending]) -> None:
    """Count a batch. The throughput plug uses this instead of writing rows."""
    global _received
    _received += len(items)


def take_received() -> int:
    global _received
    count = _received
    _received = 0
    return count


async def _report_received() -> None:
    while True:
        await asyncio.sleep(1)
        count = take_received()
        if count:
            logger.info("telemetry received %s", count)


def start_receive_counter() -> None:
    global _report_task
    if _report_task is None:
        _report_task = asyncio.create_task(_report_received(), name="telemetry-received")


async def stop_receive_counter() -> None:
    global _report_task
    task = _report_task
    _report_task = None
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def _run() -> None:
    configure_logging(settings.log_level)
    is_sqlite = settings.database_url.startswith("sqlite")
    plug = settings.throughput_plug
    logger.info("telemetry consumer throughput_plug=%s", plug)
    consumer = connect()
    batch = TelemetryBatch(
        settings.telemetry_batch_window_seconds,
        settings.telemetry_batch_max_size,
        limit=batch_max_size,
    )

    async def on_batch(items: list[Pending]) -> None:
        points = [point for point, _offset in items]
        start = time.time()
        try:
            inserted = await save_telemetry_batch(points, is_sqlite)
            logger.info("Time spent on saving telemetry batch: %s seconds", time.time() - start)
            new_start = time.time()
            await record_stored(inserted)
            logger.info("Time spent on recording stored telemetry: %s seconds", time.time() - new_start)
            await publish_batch(points)
        except Exception:
            logger.exception("failed to save telemetry batch of %s", len(items))
            for point, offset in items:
                await batch.add(point, offset)
            return
        offset = max(int(item_offset) for _point, item_offset in items)
        try:
            await consumer.store_offset(stream=STREAM, subscriber_name=SUBSCRIBER, offset=offset)
        except Exception:
            logger.exception("failed to store telemetry offset %s", offset)
        finally:
            logger.info("Time spent on on_batch: %s seconds", time.time() - start)

    async def on_message(msg: AMQPMessage, message_context: MessageContext) -> None:
        try:
            point = point_from_payload(message_body(msg.body))
        except (ValueError, OverflowError):
            logger.exception("dropped a telemetry payload")
            return
        await batch.add(point, message_context.offset)

    await consumer.start()
    try:
        await consumer.subscribe(
            stream=STREAM,
            callback=on_message,
            decoder=amqp_decoder,
            offset_specification=await resume_from(consumer),
            initial_credit=settings.telemetry_prefetch,
            subscriber_name=SUBSCRIBER,
            properties=SUBSCRIPTION,
            consumer_update_listener=on_active,
        )
        # define the callback to process the batch when on_message methods added too many to batch object.
        await batch.start(on_batch)
        if plug:
            start_receive_counter()
        await consumer.run()
    finally:
        await stop_receive_counter()
        await batch.stop()
        await consumer.close()
        await dispose_engine()
        await close_redis()


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("stopped")


if __name__ == "__main__":
    main()
