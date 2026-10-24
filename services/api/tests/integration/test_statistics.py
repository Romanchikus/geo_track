import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app
from app.schemas.telemetry import TelemetryPoint
from app.services.telemetry.processing.save import save_telemetry_batch
from tests.integration.db import add_old_point, add_subscription, delete_devices

pytestmark = pytest.mark.integration


@pytest.fixture
def client(migrated: None) -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def test_statistics_counts_recent_rows_only(client: TestClient) -> None:
    owner = f"stats-owner-{uuid.uuid4().hex}@example.com"
    email = f"stats-{uuid.uuid4().hex}@example.com"
    device_id = 0
    try:
        assert client.get("/statistics").status_code == 401

        created_owner = client.post("/users", json={"email": owner, "password": "password-1"})
        assert created_owner.status_code == 201, created_owner.text
        login = client.post("/auth/login", json={"email": owner, "password": "password-1"})
        assert login.status_code == 200, login.text

        before = client.get("/statistics")
        assert before.status_code == 200, before.text
        baseline = before.json()

        created = client.post("/users", json={"email": email, "password": "password-1"})
        assert created.status_code == 201, created.text
        device = client.post("/devices", json={"name": "stats-probe"})
        assert device.status_code == 201, device.text
        device_id = device.json()["id"]
        asyncio.run(add_subscription(created.json()["id"], device_id))

        recent = datetime.now(UTC).replace(minute=5, second=0, microsecond=0)
        asyncio.run(
            save_telemetry_batch(
                [
                    TelemetryPoint(
                        device_id=device_id,
                        latitude=50.45,
                        longitude=30.52,
                        timestamp=recent,
                    )
                ],
                settings.database_url.startswith("sqlite"),
            )
        )
        asyncio.run(add_old_point(device_id, datetime(2000, 1, 1, tzinfo=UTC)))

        response = client.get("/statistics")
        assert response.status_code == 200, response.text
        counts = response.json()
        assert counts["devices"] == baseline["devices"] + 1
        assert counts["users"] == baseline["users"] + 1
        assert counts["subscriptions"] == baseline["subscriptions"] + 1
        assert counts["telemetry"] == baseline["telemetry"] + 2
        assert counts["telemetry_last_day"] == baseline["telemetry_last_day"] + 1
    finally:
        asyncio.run(delete_devices((owner, email), device_id))
