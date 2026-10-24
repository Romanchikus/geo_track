import asyncio
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.integration.db import delete_emails

pytestmark = pytest.mark.integration


@pytest.fixture
def client(migrated: None) -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def _register(client: TestClient, email: str, password: str = "password-1") -> dict[str, object]:
    response = client.post("/users", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


async def _delete_emails(emails: tuple[str, ...]) -> None:
    await delete_emails(list(emails))


def _cleanup(emails: list[str]) -> None:
    asyncio.run(_delete_emails(tuple(emails)))


def test_user_crud_uses_session(client: TestClient) -> None:
    email = f"user-{uuid.uuid4().hex}@example.com"
    updated_email = f"next-{uuid.uuid4().hex}@example.com"
    try:
        created = _register(client, email)
        user_id = created["id"]
        assert client.get("/users/me").status_code == 401

        login = client.post("/auth/login", json={"email": email, "password": "password-1"})
        assert login.status_code == 200
        assert login.json()["email"] == email

        me = client.get("/users/me")
        assert me.status_code == 200
        assert me.json()["id"] == user_id

        listed = client.get("/users")
        assert listed.status_code == 200
        assert any(row["id"] == user_id for row in listed.json())

        updated = client.patch(
            f"/users/{user_id}",
            json={"email": updated_email, "password": "password-2"},
        )
        assert updated.status_code == 200
        assert updated.json()["email"] == updated_email

        read = client.get(f"/users/{user_id}")
        assert read.status_code == 200
        assert read.json()["email"] == updated_email

        removed = client.delete(f"/users/{user_id}")
        assert removed.status_code == 204
        assert client.get("/users/me").status_code == 401
    finally:
        _cleanup([email, updated_email])


def test_duplicate_email_is_rejected(client: TestClient) -> None:
    email = f"dup-{uuid.uuid4().hex}@example.com"
    try:
        _register(client, email)
        again = client.post("/users", json={"email": email, "password": "password-1"})
        assert again.status_code == 409
    finally:
        _cleanup([email])


def test_cannot_update_another_user(client: TestClient) -> None:
    first = f"one-{uuid.uuid4().hex}@example.com"
    second = f"two-{uuid.uuid4().hex}@example.com"
    try:
        owner = _register(client, first)
        other = _register(client, second)
        login = client.post("/auth/login", json={"email": first, "password": "password-1"})
        assert login.status_code == 200
        denied = client.patch(f"/users/{other['id']}", json={"email": f"stolen-{uuid.uuid4().hex}@example.com"})
        assert denied.status_code == 403
        unchanged = client.get(f"/users/{owner['id']}")
        assert unchanged.json()["email"] == first
    finally:
        _cleanup([first, second])
