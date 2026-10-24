import asyncio
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.db.session import dispose_engine
from app.main import create_app
from tests.integration.db import delete_emails

pytestmark = pytest.mark.integration

TRIANGLE = [[30.0, 50.0], [31.0, 50.0], [31.0, 51.0]]
SQUARE = [[10.0, 10.0], [12.0, 10.0], [12.0, 12.0], [10.0, 12.0]]


@pytest.fixture
def client(migrated: None) -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def _register(client: TestClient) -> str:
    email = f"sub-{uuid.uuid4().hex}@example.com"
    created = client.post("/users", json={"email": email, "password": "password-1"})
    assert created.status_code == 201, created.text
    login = client.post("/auth/login", json={"email": email, "password": "password-1"})
    assert login.status_code == 200, login.text
    return email


def _device(client: TestClient, name: str) -> int:
    created = client.post("/devices", json={"name": name})
    assert created.status_code == 201, created.text
    return int(created.json()["id"])


def _cleanup(emails: list[str]) -> None:
    async def go() -> None:
        # The API client binds the pool to its own loop. Drop it before this one.
        import app.db.session as db_session

        db_session._engine = None
        db_session._session_factory = None
        await delete_emails(emails)
        await dispose_engine()

    asyncio.run(go())


def test_subscription_requires_login(client: TestClient) -> None:
    assert client.get("/subscriptions").status_code == 401
    created = client.post("/subscriptions", json={"coordinates": TRIANGLE, "mode": "all"})
    assert created.status_code == 401


def test_subscription_crud_for_selected_devices(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    email = _register(client)
    device_ids: list[int] = []
    try:
        first = _device(client, "alpha")
        second = _device(client, "beta")
        third = _device(client, "gamma")
        device_ids.extend([first, second, third])
        refreshed = 0

        async def refresh() -> None:
            nonlocal refreshed
            refreshed += 1

        monkeypatch.setattr("app.services.subscriptions.crud.websocket_manager.refresh", refresh)

        missing = client.post(
            "/subscriptions",
            json={"coordinates": TRIANGLE, "mode": "ids", "device_ids": [first, 999_999_999]},
        )
        assert missing.status_code == 404

        created = client.post(
            "/subscriptions",
            json={"coordinates": TRIANGLE, "mode": "ids", "device_ids": [first, first]},
        )
        assert created.status_code == 201, created.text
        area = created.json()
        polygon_id = area["polygon_id"]
        assert area["coordinates"] == TRIANGLE
        assert [row["device_id"] for row in area["devices"]] == [first]

        other = client.post(
            "/subscriptions",
            json={"coordinates": SQUARE, "mode": "ids", "device_ids": [first, second]},
        )
        assert other.status_code == 201, other.text
        assert [row["device_id"] for row in other.json()["devices"]] == [first, second]
        assert refreshed == 2

        listed = client.get("/subscriptions")
        assert listed.status_code == 200
        assert [row["polygon_id"] for row in listed.json()] == [polygon_id, other.json()["polygon_id"]]

        read = client.get(f"/subscriptions/{polygon_id}")
        assert read.status_code == 200
        assert read.json()["devices"][0]["device_id"] == first
        assert "device_name" not in read.json()["devices"][0]

        updated = client.patch(
            f"/subscriptions/{polygon_id}",
            json={"coordinates": SQUARE, "device_ids": [first, third]},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["coordinates"] == SQUARE
        assert [row["device_id"] for row in updated.json()["devices"]] == [first, third]

        scoped = client.patch(f"/subscriptions/{polygon_id}", json={"mode": "ids", "device_ids": [third]})
        assert scoped.status_code == 200, scoped.text
        assert scoped.json()["coordinates"] == SQUARE
        assert [row["device_id"] for row in scoped.json()["devices"]] == [third]

        shared = client.patch(f"/subscriptions/{polygon_id}", json={"device_ids": [second, third]})
        assert shared.status_code == 200, shared.text
        assert {row["device_id"] for row in shared.json()["devices"]} == {second, third}
        assert refreshed == 5
        still_there = client.get(f"/subscriptions/{other.json()['polygon_id']}")
        assert [row["device_id"] for row in still_there.json()["devices"]] == [first, second]

        removed = client.delete(f"/subscriptions/{polygon_id}")
        assert removed.status_code == 204
        assert refreshed == 6
        assert client.get(f"/subscriptions/{polygon_id}").status_code == 404
        assert len(client.get("/subscriptions").json()) == 1
    finally:
        _remove_devices(client, device_ids)
        _cleanup([email])


def test_subscription_percent_picks_a_share_of_devices(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = _register(client)
    device_ids: list[int] = []

    async def only_these(_session: object) -> list[int]:
        return list(device_ids)

    monkeypatch.setattr("app.services.subscriptions.selection._available_ids", only_these)
    monkeypatch.setattr(
        "app.services.subscriptions.selection.random.sample",
        lambda population, count: list(population)[:count],
    )
    try:
        device_ids.extend(_device(client, name) for name in ("one", "two", "three", "four"))
        created = client.post("/subscriptions", json={"coordinates": TRIANGLE, "mode": "percent", "percent": 50})
        assert created.status_code == 201, created.text
        assert [row["device_id"] for row in created.json()["devices"]] == device_ids[:2]
    finally:
        _remove_devices(client, device_ids)
        _cleanup([email])


def test_subscription_all_devices_and_invalid_polygon(client: TestClient) -> None:
    email = _register(client)
    device_ids: list[int] = []
    try:
        known = client.get("/devices?limit=100").json()
        if known == []:
            empty = client.post("/subscriptions", json={"coordinates": TRIANGLE, "mode": "all"})
            assert empty.status_code == 409

        device_id = _device(client, "only")
        device_ids.append(device_id)
        if len(known) >= 99:
            created = client.post(
                "/subscriptions",
                json={"coordinates": TRIANGLE, "mode": "ids", "device_ids": [device_id]},
            )
            assert created.status_code == 201, created.text
        else:
            created = client.post("/subscriptions", json={"coordinates": TRIANGLE, "mode": "all"})
            assert created.status_code == 201, created.text
            assert device_id in {row["device_id"] for row in created.json()["devices"]}
            again = client.post("/subscriptions", json={"coordinates": SQUARE, "mode": "all"})
            assert again.status_code == 201, again.text
            assert device_id in {row["device_id"] for row in again.json()["devices"]}

        invalid = client.post(
            "/subscriptions",
            json={"coordinates": [[0.0, 0.0], [1.0, 0.0]], "mode": "ids", "device_ids": [device_id]},
        )
        assert invalid.status_code == 422
    finally:
        _remove_devices(client, device_ids)
        _cleanup([email])


def test_subscription_is_hidden_from_other_users(client: TestClient) -> None:
    owner = _register(client)
    device_id = _device(client, "owned")
    created = client.post(
        "/subscriptions",
        json={"coordinates": TRIANGLE, "mode": "ids", "device_ids": [device_id]},
    )
    assert created.status_code == 201, created.text
    polygon_id = created.json()["polygon_id"]
    client.post("/auth/logout")

    other = _register(client)
    try:
        assert client.get("/subscriptions").json() == []
        assert client.get(f"/subscriptions/{polygon_id}").status_code == 404
        denied = client.patch(f"/subscriptions/{polygon_id}", json={"device_ids": [device_id]})
        assert denied.status_code == 404
        assert client.delete(f"/subscriptions/{polygon_id}").status_code == 404
    finally:
        _remove_devices(client, [device_id])
        _cleanup([owner, other])


def _remove_devices(client: TestClient, device_ids: list[int]) -> None:
    for device_id in device_ids:
        client.delete(f"/devices/{device_id}")
