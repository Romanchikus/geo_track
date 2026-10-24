import asyncio
import contextlib
import logging
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from fastapi import WebSocket

from app.services.telemetry.live import _send_json, stream_telemetry, user_id_from_websocket
from app.services.telemetry.processing.coverage import (
    Arrival,
    Occupancy,
    arrivals_from,
    coverage_for,
    fixes_for,
    hold_occupancy,
)

logger = logging.getLogger(__name__)

_POLL = timedelta(seconds=1)
_STALE = timedelta(seconds=5)


class WebsocketManager:
    """Track live sockets by user and the union of their subscription polygons."""

    def __init__(self) -> None:
        self.connections: dict[int, set[WebSocket]] = {}
        self.polygon: str | None = None
        self.flights: list[Arrival] = []
        self.occupancy: Occupancy = {}
        self._locks: dict[WebSocket, asyncio.Lock] = {}
        self._lock = asyncio.Lock()
        self._scan = asyncio.Lock()
        self._watch_task: asyncio.Task[None] | None = None

    async def serve(self, websocket: WebSocket) -> None:
        """Register the socket, then run the live telemetry stream until it closes."""
        user_id = user_id_from_websocket(websocket)
        if user_id is None:
            await stream_telemetry(websocket)
            return
        send_lock = asyncio.Lock()

        async def on_open() -> None:
            await self._join(websocket, send_lock)

        try:
            await stream_telemetry(websocket, send_lock=send_lock, on_open=on_open)
        finally:
            await self._leave(user_id, websocket)

    async def stop(self) -> None:
        """Drop every socket and stop the point query."""
        async with self._lock:
            self.connections.clear()
            self._locks.clear()
            self.polygon = None
            self.flights = []
            self.occupancy = {}
            task = self._watch_task
            self._watch_task = None
        await _cancel(task)

    async def _join(self, websocket: WebSocket, send_lock: asyncio.Lock | None = None) -> None:
        user_id = user_id_from_websocket(websocket)
        if user_id is None:
            return
        async with self._lock:
            self.connections.setdefault(user_id, set()).add(websocket)
            self._locks[websocket] = send_lock or asyncio.Lock()
            await self._rewrite_polygon()
            self._ensure_watch()
        logger.info("telemetry socket joined user %s", user_id)

    async def _leave(self, user_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self.connections.get(user_id)
            if sockets is None or websocket not in sockets:
                return
            sockets.discard(websocket)
            self._locks.pop(websocket, None)
            if not sockets:
                del self.connections[user_id]
            await self._rewrite_polygon()
            task = None
            if not self.connections:
                task = self._watch_task
                self._watch_task = None
        logger.info("telemetry socket left user %s", user_id)
        await _cancel(task)

    async def refresh(self) -> None:
        """Reload the live polygon and push arrivals to every open socket for these users."""
        async with self._lock:
            if not self.connections:
                return
            try:
                await self._rewrite_polygon()
            except Exception:
                logger.exception("failed to refresh the live polygon")
                return
        await self.find_crosse()

    async def _rewrite_polygon(self) -> None:
        user_ids = list(self.connections)
        if not user_ids:
            self.polygon = None
            self.flights = []
            self.occupancy = {}
            logger.info("cleared live polygon")
            return
        polygon = await coverage_for(user_ids)
        self.polygon = polygon
        self.occupancy = {}
        if self.polygon is None:
            logger.info("live polygon is empty for %s users", len(user_ids))
            return
        logger.info("rewrote live polygon for %s users", len(user_ids))

    def _ensure_watch(self) -> None:
        if self._watch_task is None:
            self._watch_task = asyncio.create_task(self._watch(), name="telemetry-sockets")

    async def _watch(self) -> None:
        while self._watch_task is asyncio.current_task() and self.connections:
            await asyncio.sleep(_POLL.total_seconds())
            if self._watch_task is not asyncio.current_task() or not self.connections:
                return
            await self.find_crosse()

    async def find_crosse(self) -> list[Arrival]:
        """Return each device still inside a subscribed area.

        A device stays until a newer fix is outside its polygon, or the last fix is older
        than the stale limit. Missing a second at 9-11k points/s does not drop it.
        """
        async with self._scan:
            polygon = self.polygon
            user_ids = list(self.connections)
            stale_before = _now() - _STALE
            if polygon is None or not user_ids:
                self.occupancy = {}
                await self._replace_flights([])
                return []
            try:
                fixes = await fixes_for(user_ids, stale_before)
            except Exception:
                logger.exception("failed to query devices inside the live polygon")
                self.occupancy = hold_occupancy(self.occupancy, [], stale_before, set(user_ids))
                flights = arrivals_from(self.occupancy)
                await self._replace_flights(flights)
                return flights
            self.occupancy = hold_occupancy(self.occupancy, fixes, stale_before, set(user_ids))
            flights = arrivals_from(self.occupancy)
            await self._replace_flights(flights)
            return flights

    async def _replace_flights(self, flights: list[Arrival]) -> None:
        previous = len(self.flights)
        self.flights = flights
        if flights:
            logger.info("devices inside %s subscription areas", len(flights))
        elif previous:
            logger.info("no devices left inside subscription areas")
        await self.notify_arrivals(flights)

    async def notify_arrivals(self, arrivals: list[Arrival]) -> None:
        """Send each user the devices currently inside their areas."""
        for user_id, sockets in list(self.connections.items()):
            user_arrivals = [arrival for arrival in arrivals if arrival.user_id == user_id]
            message: dict[str, object] = {
                "type": "arrivals",
                "data": [asdict(arrival) for arrival in user_arrivals],
            }
            for websocket in list(sockets):
                try:
                    await _send_json(websocket, message, self._locks.get(websocket))
                except Exception:
                    logger.info("closed a live telemetry socket for user %s", user_id)
                    await self._leave(user_id, websocket)


websocket_manager = WebsocketManager()


def _now() -> datetime:
    return datetime.now(UTC)


async def _cancel(task: asyncio.Task[None] | None) -> None:
    if task is None or task is asyncio.current_task():
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
