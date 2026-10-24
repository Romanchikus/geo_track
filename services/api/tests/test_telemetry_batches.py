import asyncio
import struct
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_db
from app.main import create_app
from app.schemas.telemetry import TelemetryPoint
from app.services.telemetry.batches import BatchMissingError, batch_body, latest_batch_id, publish_batch
from app.services.telemetry.pack import pack_points


@pytest.fixture(autouse=True)
def _reset_open_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.telemetry.batches._open_second", -1)
    monkeypatch.setattr("app.services.telemetry.batches._open_id", None)


class _Text:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.seq = 0

    async def incr(self, key: str) -> int:
        del key
        self.seq += 1
        return self.seq

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        del ex
        self.values[key] = value

    async def get(self, key: str) -> str | None:
        return self.values.get(key)


class _Binary:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}
        self.sets = 0

    async def get(self, key: str) -> bytes | None:
        return self.values.get(key)

    async def set(self, key: str, value: bytes, ex: int | None = None) -> None:
        del ex
        self.sets += 1
        self.values[key] = value

    async def append(self, key: str, value: bytes) -> None:
        self.values[key] = self.values.get(key, b"") + value

    async def expire(self, key: str, seconds: int) -> None:
        del key, seconds


def test_pack_points_uses_a_20_byte_record() -> None:
    stamp = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    body = pack_points([TelemetryPoint(device_id=7, latitude=55.75, longitude=37.61, timestamp=stamp)])

    device_id, latitude, longitude, seconds = struct.unpack("<qffI", body)

    assert len(body) == 20
    assert device_id == 7
    assert latitude == pytest.approx(55.75, abs=1e-4)
    assert longitude == pytest.approx(37.61, abs=1e-4)
    assert seconds == int(stamp.timestamp())


async def test_batch_body_returns_the_stored_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    text = _Text()
    binary = _Binary()
    monkeypatch.setattr("app.services.telemetry.batches.get_redis", lambda: text)
    monkeypatch.setattr("app.services.telemetry.batches.get_binary_redis", lambda: binary)
    stamp = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    point = TelemetryPoint(device_id=7, latitude=55.75, longitude=37.61, timestamp=stamp)

    batch_id = await publish_batch([point])
    assert batch_id == 1
    first = await batch_body(batch_id)
    second = await batch_body(batch_id)

    assert first == second == pack_points([point])
    assert binary.sets == 1


async def test_missing_batch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.telemetry.batches.get_binary_redis", lambda: _Binary())

    with pytest.raises(BatchMissingError):
        await batch_body(3)


def test_batch_endpoint_returns_the_stored_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    text = _Text()
    binary = _Binary()
    monkeypatch.setattr("app.services.telemetry.batches.get_redis", lambda: text)
    monkeypatch.setattr("app.services.telemetry.batches.get_binary_redis", lambda: binary)
    stamp = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    point = TelemetryPoint(device_id=7, latitude=55.75, longitude=37.61, timestamp=stamp)
    batch_id = asyncio.run(publish_batch([point]))
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: object()

    assert batch_id is not None
    with TestClient(app) as client:
        first = client.get(f"/telemetry/batches/{batch_id}")
        second = client.get(f"/telemetry/batches/{batch_id}")
        missing = client.get("/telemetry/batches/99")

    assert first.status_code == 200, first.text
    assert first.headers["content-type"].startswith("application/octet-stream")
    assert first.content == pack_points([point])
    assert second.content == first.content
    assert binary.sets == 1
    assert missing.status_code == 404


async def test_batch_id_increments_once_per_second(monkeypatch: pytest.MonkeyPatch) -> None:
    text = _Text()
    binary = _Binary()
    clock = {"now": 1_000.1}
    monkeypatch.setattr("app.services.telemetry.batches.get_redis", lambda: text)
    monkeypatch.setattr("app.services.telemetry.batches.get_binary_redis", lambda: binary)
    monkeypatch.setattr("app.services.telemetry.batches.time.time", lambda: clock["now"])
    first = TelemetryPoint(device_id=7, latitude=55.75, longitude=37.61, timestamp=datetime(2026, 10, 24, tzinfo=UTC))
    second = TelemetryPoint(device_id=8, latitude=48.85, longitude=2.35, timestamp=datetime(2026, 10, 24, tzinfo=UTC))

    opened = await publish_batch([first])
    again = await publish_batch([second])

    assert opened == again == 1
    assert await latest_batch_id() is None
    assert await batch_body(1) == pack_points([first]) + pack_points([second])

    clock["now"] = 1_001.2
    third = TelemetryPoint(device_id=9, latitude=40.7, longitude=-74.0, timestamp=datetime(2026, 10, 24, tzinfo=UTC))
    nxt = await publish_batch([third])

    assert nxt == 2
    assert await latest_batch_id() == 1
    assert text.seq == 2


def test_batch_endpoint_requires_login() -> None:
    async def empty_db() -> AsyncIterator[object]:
        yield object()

    app = create_app()
    app.dependency_overrides[get_db] = empty_db

    with TestClient(app) as client:
        response = client.get("/telemetry/batches/1")

    assert response.status_code == 401
