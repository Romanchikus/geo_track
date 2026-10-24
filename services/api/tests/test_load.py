from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

from app.api.dependencies import get_db
from app.core.config import settings
from app.main import create_app
from app.services import load as load_service


class _Redis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str) -> None:
        self.values[key] = value

    async def mget(self, *keys: str) -> list[str | None]:
        return [self.values.get(key) for key in keys]


class _Down:
    async def get(self, key: str) -> str | None:
        raise RedisError("down")

    async def set(self, key: str, value: str) -> None:
        raise RedisError("down")

    async def mget(self, *keys: str) -> list[str | None]:
        raise RedisError("down")


def _client() -> TestClient:
    app = create_app()

    async def empty_db() -> AsyncIterator[object]:
        yield object()

    app.dependency_overrides[get_db] = empty_db
    return TestClient(app)


def _reset_batch() -> None:
    load_service._reported_batch = None
    load_service._batch_down = False
    load_service._bad_batch = None


def test_load_patch_stores_speed_and_batch_size(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = _Redis()
    monkeypatch.setattr("app.services.load.get_redis", lambda: redis)
    headers = {"X-Internal-Token": settings.internal_token}

    with _client() as client:
        denied = client.patch("/load", json={"speed_kmh": 80})
        empty = client.patch("/load", json={}, headers=headers)
        updated = client.patch(
            "/load",
            json={"speed_kmh": 80, "telemetry_batch_max_size": 2500},
            headers=headers,
        )
        kept = client.patch("/load", json={"speed_kmh": 120}, headers=headers)
        current = client.get("/load", headers=headers)

    assert denied.status_code == 401
    assert empty.status_code == 422
    assert updated.status_code == 200
    assert updated.json() == {"speed_kmh": 80.0, "telemetry_batch_max_size": 2500}
    assert kept.json() == {"speed_kmh": 120.0, "telemetry_batch_max_size": 2500}
    assert current.json() == kept.json()
    assert redis.values["load:telemetry_batch_max_size"] == "2500"


def test_load_reports_unavailable_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.load.get_redis", lambda: _Down())
    headers = {"X-Internal-Token": settings.internal_token}

    with _client() as client:
        response = client.get("/load", headers=headers)

    assert response.status_code == 503


async def test_batch_max_size_follows_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = _Redis()
    monkeypatch.setattr("app.services.load.get_redis", lambda: redis)
    monkeypatch.setattr(settings, "telemetry_batch_max_size", 1000)
    _reset_batch()

    assert await load_service.batch_max_size() == 1000
    redis.values["load:telemetry_batch_max_size"] = "4000"
    assert await load_service.batch_max_size() == 4000
    redis.values["load:telemetry_batch_max_size"] = "nope"
    assert await load_service.batch_max_size() == 1000
