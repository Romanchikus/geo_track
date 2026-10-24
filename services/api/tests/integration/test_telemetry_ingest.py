from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.models.device import Device
from app.db.models.telemetry import Telemetry
from app.db.session import dispose_engine, get_session_factory
from app.schemas.telemetry import TelemetryPoint
from app.services.telemetry.processing.save import save_telemetry_batch

pytestmark = pytest.mark.integration


async def test_save_telemetry_batch_keeps_valid_points(migrated: None) -> None:
    factory = get_session_factory()
    device_id = 0
    try:
        async with factory() as session:
            device = Device(name="ingest")
            session.add(device)
            await session.commit()
            device_id = device.id
        stamp = datetime.now(UTC).replace(second=0, microsecond=0)
        later = stamp + timedelta(minutes=1)
        newest = later + timedelta(minutes=1)
        sqlite = settings.database_url.startswith("sqlite")
        first = TelemetryPoint(device_id=device_id, latitude=55.75, longitude=37.61, timestamp=stamp)
        second = TelemetryPoint(device_id=device_id, latitude=55.76, longitude=37.62, timestamp=later)
        saved = await save_telemetry_batch([first, second], sqlite)
        assert saved == 2
        assert await _count(device_id) == 2
        assert await _location(device_id, stamp) == "POINT(37.61 55.75)"
        assert await _location(device_id, later) == "POINT(37.62 55.76)"

        again = await save_telemetry_batch(
            [TelemetryPoint(device_id=device_id, latitude=1, longitude=2, timestamp=stamp)],
            sqlite,
        )
        assert again == 0
        assert await _count(device_id) == 2
        assert await _location(device_id, stamp) == "POINT(37.61 55.75)"

        mixed = await save_telemetry_batch(
            [
                TelemetryPoint(device_id=device_id, latitude=1, longitude=2, timestamp=stamp),
                TelemetryPoint(device_id=device_id, latitude=55.75, longitude=37.61, timestamp=stamp),
                TelemetryPoint(device_id=device_id, latitude=10, longitude=20, timestamp=newest),
            ],
            sqlite,
        )
        assert mixed == 1
        assert await _count(device_id) == 3
        assert await _location(device_id, stamp) == "POINT(37.61 55.75)"
        assert await _location(device_id, newest) == "POINT(20.0 10.0)"

        with pytest.raises(IntegrityError):
            await save_telemetry_batch(
                [TelemetryPoint(device_id=999_999_999, latitude=1, longitude=2, timestamp=stamp)],
                sqlite,
            )
        assert await _count(device_id) == 3

        with pytest.raises(IntegrityError):
            await save_telemetry_batch(
                [
                    TelemetryPoint(
                        device_id=device_id,
                        latitude=10,
                        longitude=20,
                        timestamp=newest + timedelta(minutes=1),
                    ),
                    TelemetryPoint(device_id=999_999_999, latitude=1, longitude=2, timestamp=later),
                ],
                sqlite,
            )
        assert await _count(device_id) == 3
    finally:
        async with factory() as session:
            if device_id:
                await session.execute(delete(Telemetry).where(Telemetry.device_id == device_id))
                await session.execute(delete(Device).where(Device.id == device_id))
                await session.commit()
        await dispose_engine()


async def test_save_telemetry_batch_stores_every_page(migrated: None) -> None:
    factory = get_session_factory()
    device_id = 0
    try:
        async with factory() as session:
            device = Device(name="ingest-pages")
            session.add(device)
            await session.commit()
            device_id = device.id
        stamp = datetime.now(UTC).replace(second=0, microsecond=0)
        sqlite = settings.database_url.startswith("sqlite")
        points = [
            TelemetryPoint(
                device_id=device_id,
                latitude=55.75,
                longitude=37.61,
                timestamp=stamp + timedelta(seconds=index),
            )
            for index in range(5_001)
        ]
        saved = await save_telemetry_batch(points, sqlite)
        assert saved == 5_001
        assert await _count(device_id) == 5_001
        again = await save_telemetry_batch(points, sqlite)
        assert again == 0
        assert await _count(device_id) == 5_001
        assert await _location(device_id, stamp) == "POINT(37.61 55.75)"
    finally:
        async with factory() as session:
            if device_id:
                await session.execute(delete(Telemetry).where(Telemetry.device_id == device_id))
                await session.execute(delete(Device).where(Device.id == device_id))
                await session.commit()
        await dispose_engine()


async def _count(device_id: int) -> int:
    factory = get_session_factory()
    async with factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(Telemetry).where(Telemetry.device_id == device_id)
        )
        return int(count or 0)


async def _location(device_id: int, stamp: datetime) -> str:
    factory = get_session_factory()
    async with factory() as session:
        value = await session.scalar(
            select(Telemetry.location).where(Telemetry.device_id == device_id, Telemetry.timestamp == stamp)
        )
    return str(value)
