import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.config import settings
from app.db.models.device import Device
from app.db.models.telemetry import Telemetry
from app.db.session import dispose_engine, get_session_factory
from app.main import create_app
from app.schemas.telemetry import TelemetryPoint
from app.services.telemetry.processing.save import save_telemetry_batch
from tests.integration.db import delete_device_tree

pytestmark = pytest.mark.integration


@pytest.fixture
def client(migrated: None) -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def _login(client: TestClient) -> str:
    email = f"device-{uuid.uuid4().hex}@example.com"
    created = client.post("/users", json={"email": email, "password": "password-1"})
    assert created.status_code == 201, created.text
    login = client.post("/auth/login", json={"email": email, "password": "password-1"})
    assert login.status_code == 200, login.text
    return email


def test_device_batch_and_list_all(client: TestClient) -> None:
    assert client.get("/devices/all").status_code == 401
    assert client.post("/devices/batch", json={"count": 2}).status_code == 401
    email = _login(client)
    device_ids: list[int] = []
    try:
        created = client.post("/devices/batch", json={"count": 2})
        assert created.status_code == 201, created.text
        device_ids = [row["id"] for row in created.json()]
        assert len(device_ids) == 2
        listed = client.get("/devices/all")
        assert listed.status_code == 200, listed.text
        listed_ids = {row["id"] for row in listed.json()}
        assert set(device_ids) <= listed_ids
    finally:
        for device_id in device_ids:
            _cleanup(email, device_id)


def test_devices_and_telemetry_crud(client: TestClient) -> None:
    assert client.get("/devices").status_code == 401
    email = _login(client)
    stamp = datetime.now(UTC).replace(minute=10, second=0, microsecond=0)
    later = stamp + timedelta(minutes=5)
    device_id = 0
    try:
        created = client.post("/devices", json={"name": "truck-1"})
        assert created.status_code == 201, created.text
        device_id = created.json()["id"]
        assert created.json()["name"] == "truck-1"

        listed = client.get("/devices")
        assert listed.status_code == 200
        assert any(row["id"] == device_id for row in listed.json())

        renamed = client.patch(f"/devices/{device_id}", json={"name": "truck-2"})
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "truck-2"
        assert client.get(f"/devices/{device_id}").json()["name"] == "truck-2"

        body = [
            {
                "device_id": device_id,
                "latitude": 55.75,
                "longitude": 37.61,
                "timestamp": stamp.isoformat(),
            },
            {
                "device_id": device_id,
                "latitude": 55.76,
                "longitude": 37.62,
                "timestamp": later.isoformat(),
            },
        ]
        asyncio.run(_save(body))

        duplicate_body = [
            {
                "device_id": device_id,
                "latitude": 1,
                "longitude": 2,
                "timestamp": stamp.isoformat(),
            }
        ]
        asyncio.run(_save(duplicate_body))

        found = client.get(f"/telemetry/{device_id}/{stamp.isoformat()}")
        assert found.status_code == 200, found.text
        assert found.json()["latitude"] == pytest.approx(55.75)

        listed_points = client.get("/telemetry", params={"device_id[eq]": device_id})
        assert listed_points.status_code == 200, listed_points.text
        assert len(listed_points.json()) == 2

        later_only = client.get(
            "/telemetry",
            params={"device_id[eq]": device_id, "timestamp[ge]": later.isoformat()},
        )
        assert later_only.status_code == 200, later_only.text
        assert len(later_only.json()) == 1
        assert later_only.json()[0]["longitude"] == pytest.approx(37.62)

        paged = client.get(
            "/telemetry",
            params={"device_id[eq]": device_id, "limit": 1, "offset": 1},
        )
        assert paged.status_code == 200, paged.text
        assert len(paged.json()) == 1
        assert paged.json()[0]["longitude"] == pytest.approx(37.62)

        blocked = client.delete(f"/devices/{device_id}")
        assert blocked.status_code == 409
    finally:
        _cleanup(email, device_id)


async def test_telemetry_insert_rolls_back(migrated: None) -> None:
    factory = get_session_factory()
    device_id = 0
    try:
        async with factory() as session:
            device = Device(name="rollback")
            session.add(device)
            await session.commit()
            device_id = device.id
        stamp = datetime.now(UTC).replace(second=0, microsecond=0)
        async with factory() as session:
            session.add(Telemetry(device_id=device_id, location="POINT(1 2)", timestamp=stamp))
            await session.flush()
            await session.rollback()
        async with factory() as session:
            count = await session.scalar(
                select(func.count()).select_from(Telemetry).where(Telemetry.device_id == device_id)
            )
            assert count == 0
    finally:
        async with factory() as session:
            if device_id:
                await session.execute(delete(Device).where(Device.id == device_id))
                await session.commit()
        await dispose_engine()


def _cleanup(email: str, device_id: int) -> None:
    asyncio.run(delete_device_tree(email, device_id))


async def _save(body: list[dict[str, object]]) -> None:
    sqlite = settings.database_url.startswith("sqlite")
    await save_telemetry_batch([TelemetryPoint.model_validate(point) for point in body], sqlite)
