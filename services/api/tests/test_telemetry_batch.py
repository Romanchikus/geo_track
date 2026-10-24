import asyncio
from datetime import UTC, datetime

from app.schemas.telemetry import TelemetryPoint
from app.services.telemetry.processing.batch import Pending, TelemetryBatch
from app.services.telemetry.processing.broker import count_batch, take_received


def _points(count: int) -> list[TelemetryPoint]:
    stamp = datetime(2026, 10, 22, 18, 0, tzinfo=UTC)
    return [TelemetryPoint(device_id=index, latitude=50.45, longitude=30.52, timestamp=stamp) for index in range(count)]


async def test_window_flushes_fewer_or_more_than_one_thousand() -> None:
    batch = TelemetryBatch(0.05, max_batch_size=2_000)
    seen: list[int] = []

    async def flush(items: list[Pending]) -> None:
        seen.append(len(items))

    await batch.start(flush)
    try:
        for point in _points(2):
            await batch.add(point, point.device_id)
        await asyncio.sleep(0)
        assert seen == []
        await asyncio.sleep(0.15)
        assert seen == [2]

        for point in _points(1001):
            await batch.add(point, point.device_id)
        await asyncio.sleep(0.15)
        assert seen == [2, 1001]
    finally:
        await batch.stop()


async def test_full_batch_flushes_before_the_window() -> None:
    batch = TelemetryBatch(30, max_batch_size=4)
    seen: list[int] = []
    done = asyncio.Event()

    async def flush(items: list[Pending]) -> None:
        seen.append(len(items))
        done.set()

    await batch.start(flush)
    try:
        for point in _points(3):
            await batch.add(point, point.device_id)
        await asyncio.sleep(0)
        assert seen == []

        await batch.add(_points(1)[0], 3)
        await asyncio.wait_for(done.wait(), timeout=1)
        assert seen == [4]
    finally:
        await batch.stop()


async def test_redis_limit_flushes_before_the_window() -> None:
    async def limit() -> int:
        return 2

    batch = TelemetryBatch(30, limit=limit)
    seen: list[int] = []
    done = asyncio.Event()

    async def flush(items: list[Pending]) -> None:
        seen.append(len(items))
        done.set()

    await batch.start(flush)
    try:
        await asyncio.sleep(0)
        for point in _points(2):
            await batch.add(point, point.device_id)
        await asyncio.wait_for(done.wait(), timeout=1)
        assert seen == [2]
    finally:
        await batch.stop()


async def test_stop_flushes_the_open_window() -> None:
    batch = TelemetryBatch(30)
    seen: list[int] = []

    async def flush(items: list[Pending]) -> None:
        seen.append(len(items))

    await batch.start(flush)
    await batch.add(_points(1)[0], "message")
    await batch.stop()

    assert seen == [1]


async def test_count_batch_counts() -> None:
    take_received()
    await count_batch([(_points(1)[0], 1)])

    assert take_received() == 1
