import asyncio
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app
from tests.integration.db import delete_device_tree, delete_emails

pytestmark = pytest.mark.integration


@pytest.fixture
def client(migrated: None) -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def test_internal_token_lists_and_creates_devices(client: TestClient) -> None:
    headers = {"X-Internal-Token": settings.internal_token}
    device_id = 0
    try:
        created = client.post("/devices/batch", json={"count": 1}, headers=headers)
        assert created.status_code == 201, created.text
        device_id = created.json()[0]["id"]
        listed = client.get("/devices/all", headers=headers)
        assert listed.status_code == 200, listed.text
        assert any(row["id"] == device_id for row in listed.json())
    finally:
        asyncio.run(delete_device_tree("rate-cleanup@example.com", device_id))


def test_live_socket_sends_requests_from_the_last_window(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def stored(now: float | None = None) -> int:
        del now
        return 1

    async def total() -> int:
        return 9

    async def batch() -> int | None:
        return 4

    monkeypatch.setattr("app.services.telemetry.live.stored_last_second", stored)
    monkeypatch.setattr("app.services.telemetry.live.stored_total", total)
    monkeypatch.setattr("app.services.telemetry.live.latest_batch_id", batch)
    email = f"live-{uuid.uuid4().hex}@example.com"
    try:
        created = client.post("/users", json={"email": email, "password": "password-1"})
        assert created.status_code == 201, created.text
        login = client.post("/auth/login", json={"email": email, "password": "password-1"})
        assert login.status_code == 200, login.text
        with client.websocket_connect("/telemetry/live") as websocket:
            assert websocket.receive_json() == {
                "stored": 1,
                "stored_total": 9,
                "batch": 4,
            }
    finally:
        asyncio.run(delete_emails([email]))
