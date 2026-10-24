import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from fastapi import WebSocket
from shapely.wkt import loads
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.telemetry.processing.coverage import (
    Arrival,
    Fix,
    _postgres_fixes,
    _postgres_union,
    hold_occupancy,
    merged_polygon,
)
from app.services.telemetry.processing.sockets import _STALE, WebsocketManager


class _Socket:
    def __init__(self, user_id: int | None) -> None:
        self.scope: dict[str, object] = {} if user_id is None else {"session": {"user_id": user_id}}
        self.sent: list[dict[str, object]] = []

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)


def test_postgres_coverage_is_a_database_union() -> None:
    compiled = str(_postgres_union([1, 2]).compile(dialect=postgresql.dialect())).lower()
    assert "st_unaryunion" in compiled
    assert "st_collect" in compiled
    assert "subscriptions" in compiled
    fixes = _postgres_fixes([1], datetime(2026, 1, 1, tzinfo=UTC))
    compiled_fixes = str(fixes.compile(dialect=postgresql.dialect())).lower()
    assert "subscriptions.user_id" in compiled_fixes
    assert "subscriptions.device_id" in compiled_fixes
    assert "subscriptions.polygon_id" in compiled_fixes
    assert "st_covers" in compiled_fixes
    assert "lateral" in compiled_fixes
    assert "order by" in compiled_fixes
    assert "limit" in compiled_fixes
    assert "st_geogfromtext" not in compiled_fixes
    assert "st_intersects" not in compiled_fixes


async def test_sockets_follow_users_and_rewrite_the_polygon(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[int]] = []

    async def coverage(user_ids: list[int]) -> str | None:
        seen.append(sorted(user_ids))
        return "POLYGON((0 0, 1 0, 1 1, 0 0))"

    monkeypatch.setattr("app.services.telemetry.processing.sockets.coverage_for", coverage)
    manager = WebsocketManager()
    first = cast(WebSocket, _Socket(1))
    second = cast(WebSocket, _Socket(2))
    try:
        await manager._join(first)
        await manager._join(second)
        assert set(manager.connections) == {1, 2}
        assert manager.polygon is not None
        await manager._leave(1, first)
        assert set(manager.connections) == {2}
        await manager._leave(2, second)
        assert manager.connections == {}
        assert manager.polygon is None
    finally:
        await manager.stop()
    assert seen == [[1], [1, 2], [2]]


async def test_serve_drops_the_user_when_the_stream_ends(monkeypatch: pytest.MonkeyPatch) -> None:
    async def coverage(user_ids: list[int]) -> str | None:
        return "POLYGON((0 0, 1 0, 1 1, 0 0))" if user_ids else None

    async def stream(
        websocket: WebSocket,
        send_lock: asyncio.Lock | None = None,
        on_open: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        del websocket, send_lock
        assert on_open is not None
        await on_open()

    monkeypatch.setattr("app.services.telemetry.processing.sockets.coverage_for", coverage)
    monkeypatch.setattr("app.services.telemetry.processing.sockets.stream_telemetry", stream)
    manager = WebsocketManager()
    socket = cast(WebSocket, _Socket(4))
    await manager.serve(socket)
    assert manager.connections == {}
    assert manager.polygon is None
    assert manager._watch_task is None


async def test_refresh_replaces_the_live_polygon_after_a_redraw(monkeypatch: pytest.MonkeyPatch) -> None:
    polygons = iter(["POLYGON((0 0, 1 0, 1 1, 0 0))", "POLYGON((2 2, 3 2, 3 3, 2 2))"])

    async def coverage(user_ids: list[int]) -> str | None:
        assert user_ids == [7]
        return next(polygons)

    async def fixes(user_ids: list[int], since: datetime) -> list[Fix]:
        del user_ids, since
        return []

    monkeypatch.setattr("app.services.telemetry.processing.sockets.coverage_for", coverage)
    monkeypatch.setattr("app.services.telemetry.processing.sockets.fixes_for", fixes)
    manager = WebsocketManager()
    socket = cast(WebSocket, _Socket(7))
    try:
        await manager._join(socket)
        assert manager.polygon == "POLYGON((0 0, 1 0, 1 1, 0 0))"
        await manager.refresh()
        assert manager.polygon == "POLYGON((2 2, 3 2, 3 3, 2 2))"
    finally:
        await manager.stop()
    manager.polygon = "POLYGON((0 0, 1 0, 1 1, 0 0))"
    await manager.refresh()
    assert manager.polygon == "POLYGON((0 0, 1 0, 1 1, 0 0))"


async def test_refresh_pushes_arrivals_to_every_open_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 6, 1, tzinfo=UTC)

    async def coverage(user_ids: list[int]) -> str | None:
        assert user_ids == [7]
        return "POLYGON((2 2, 3 2, 3 3, 2 2))"

    async def fixes(user_ids: list[int], since: datetime) -> list[Fix]:
        del user_ids, since
        return [Fix(7, 9, 4, now, True)]

    monkeypatch.setattr("app.services.telemetry.processing.sockets.coverage_for", coverage)
    monkeypatch.setattr("app.services.telemetry.processing.sockets.fixes_for", fixes)
    monkeypatch.setattr("app.services.telemetry.processing.sockets._now", lambda: now)
    manager = WebsocketManager()
    first = _Socket(7)
    second = _Socket(7)
    try:
        await manager._join(cast(WebSocket, first))
        await manager._join(cast(WebSocket, second))
        first.sent.clear()
        second.sent.clear()
        manager.occupancy = {(7, 3, 1): now}
        await manager.refresh()
        payload = {"type": "arrivals", "data": [{"user_id": 7, "device_id": 9, "polygon_id": 4}]}
        assert first.sent == [payload]
        assert second.sent == [payload]
        assert manager.flights == [Arrival(7, 9, 4)]
    finally:
        await manager.stop()


async def test_one_user_keeps_every_open_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    async def coverage(user_ids: list[int]) -> str | None:
        assert user_ids == [7]
        return "POLYGON((0 0, 1 0, 1 1, 0 0))"

    monkeypatch.setattr("app.services.telemetry.processing.sockets.coverage_for", coverage)
    manager = WebsocketManager()
    first = cast(WebSocket, _Socket(7))
    second = cast(WebSocket, _Socket(7))
    try:
        await manager._join(first)
        await manager._join(second)
        assert manager.connections == {7: {first, second}}
        await manager._leave(7, first)
        assert manager.connections == {7: {second}}
    finally:
        await manager.stop()


async def test_publish_sends_the_devices_still_inside(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 6, 1, tzinfo=UTC)

    async def fixes(user_ids: list[int], since: datetime) -> list[Fix]:
        assert user_ids == [7]
        assert since == now - _STALE
        return [Fix(7, 9, 3, now, True)]

    monkeypatch.setattr("app.services.telemetry.processing.sockets.fixes_for", fixes)
    monkeypatch.setattr("app.services.telemetry.processing.sockets._now", lambda: now)
    manager = WebsocketManager()
    manager.polygon = "POLYGON((0 0, 1 0, 1 1, 0 0))"
    first = _Socket(7)
    second = _Socket(7)
    manager.connections = {7: {cast(WebSocket, first), cast(WebSocket, second)}}
    found = await manager.find_crosse()
    payload = {"type": "arrivals", "data": [{"user_id": 7, "device_id": 9, "polygon_id": 3}]}
    assert found == [Arrival(7, 9, 3)]
    assert manager.flights == found
    assert first.sent == [payload]
    assert second.sent == [payload]


async def test_a_missed_second_keeps_the_plane_until_a_newer_fix_leaves(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 6, 1, tzinfo=UTC)
    clock = {"now": now}
    batches: list[list[Fix]] = [
        [Fix(7, 9, 3, now, True)],
        [],
        [Fix(7, 9, 3, now + timedelta(seconds=2), False)],
    ]

    async def fixes(user_ids: list[int], since: datetime) -> list[Fix]:
        del user_ids, since
        return batches.pop(0)

    monkeypatch.setattr("app.services.telemetry.processing.sockets.fixes_for", fixes)
    monkeypatch.setattr("app.services.telemetry.processing.sockets._now", lambda: clock["now"])
    manager = WebsocketManager()
    manager.polygon = "POLYGON((0 0, 1 0, 1 1, 0 0))"
    socket = _Socket(7)
    manager.connections = {7: {cast(WebSocket, socket)}}

    assert await manager.find_crosse() == [Arrival(7, 9, 3)]
    assert await manager.find_crosse() == [Arrival(7, 9, 3)]
    assert socket.sent[-1]["data"] == [{"user_id": 7, "device_id": 9, "polygon_id": 3}]
    assert await manager.find_crosse() == []
    assert socket.sent[-1] == {"type": "arrivals", "data": []}


async def test_a_stale_fix_leaves_the_area(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 6, 1, tzinfo=UTC)
    clock = {"now": now}

    async def fixes(user_ids: list[int], since: datetime) -> list[Fix]:
        del user_ids, since
        return []

    monkeypatch.setattr("app.services.telemetry.processing.sockets.fixes_for", fixes)
    monkeypatch.setattr("app.services.telemetry.processing.sockets._now", lambda: clock["now"])
    manager = WebsocketManager()
    manager.polygon = "POLYGON((0 0, 1 0, 1 1, 0 0))"
    manager.occupancy = {(7, 9, 3): now}
    socket = _Socket(7)
    manager.connections = {7: {cast(WebSocket, socket)}}
    clock["now"] = now + _STALE + timedelta(seconds=1)
    assert await manager.find_crosse() == []
    assert socket.sent == [{"type": "arrivals", "data": []}]


async def test_a_failed_area_query_keeps_a_fresh_fix(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 6, 1, tzinfo=UTC)

    async def fixes(user_ids: list[int], since: datetime) -> list[Fix]:
        del user_ids, since
        raise RuntimeError("coverage query failed")

    monkeypatch.setattr("app.services.telemetry.processing.sockets.fixes_for", fixes)
    monkeypatch.setattr("app.services.telemetry.processing.sockets._now", lambda: now)
    manager = WebsocketManager()
    manager.polygon = "POLYGON((0 0, 1 0, 1 1, 0 0))"
    manager.occupancy = {(7, 9, 3): now}
    socket = _Socket(7)
    manager.connections = {7: {cast(WebSocket, socket)}}
    assert await manager.find_crosse() == [Arrival(7, 9, 3)]
    assert socket.sent == [{"type": "arrivals", "data": [{"user_id": 7, "device_id": 9, "polygon_id": 3}]}]


class _Dialect:
    name = "sqlite"


class _Bind:
    dialect = _Dialect()


class _Values:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def all(self) -> list[object]:
        return self._values


class _Shapes:
    def __init__(self, polygons: list[str]) -> None:
        self.polygons = polygons

    def get_bind(self) -> _Bind:
        return _Bind()

    async def scalars(self, statement: object) -> _Values:
        del statement
        return _Values(list(self.polygons))


async def test_sqlite_union_keeps_each_area() -> None:
    west = "POLYGON((0 0, 2 0, 2 2, 0 2, 0 0))"
    east = "POLYGON((10 10, 12 10, 12 12, 10 12, 10 10))"
    session = cast(AsyncSession, _Shapes([west, east]))
    merged = await merged_polygon(session, [1, 2])
    assert merged is not None
    shape = loads(merged)
    assert shape.covers(loads("POINT(1 1)"))
    assert shape.covers(loads("POINT(11 11)"))


def test_occupancy_ignores_a_quiet_second_and_an_older_point() -> None:
    seen = datetime(2024, 1, 1, tzinfo=UTC)
    held = {(1, 7, 3): seen}
    users = {1}
    assert hold_occupancy(held, [], seen, users) == held
    older_outside = Fix(1, 7, 3, seen - timedelta(seconds=1), False)
    assert hold_occupancy(held, [older_outside], seen - timedelta(seconds=5), users) == held
    left = Fix(1, 7, 3, seen + timedelta(seconds=1), False)
    assert hold_occupancy(held, [left], seen, users) == {}
    assert hold_occupancy(held, [], seen + timedelta(seconds=1), users) == {}
