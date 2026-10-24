import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.schemas.telemetry import TelemetryPoint

logger = logging.getLogger(__name__)

Pending = tuple[TelemetryPoint, Any]
Flush = Callable[[list[Pending]], Awaitable[None]]


class TelemetryBatch:
    """Flush on a fixed time window, or sooner when the buffer is full."""

    def __init__(
        self,
        window_seconds: float,
        max_batch_size: int = 500,
        limit: Callable[[], Awaitable[int]] | None = None,
    ) -> None:
        self._window_seconds = window_seconds
        self._max_batch_size = max_batch_size
        self._limit = limit
        self._pending: list[Pending] = []
        self._lock = asyncio.Lock()
        # Added the _wake to run tasks immediately when messages are added to the buffer.
        # _wake.set() will wake up the _loop task to flush the points.
        self._wake = asyncio.Event()
        self._flush: Flush | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def add(self, point: TelemetryPoint, message: Any) -> None:
        async with self._lock:
            self._pending.append((point, message))
            if len(self._pending) >= self._max_batch_size:
                self._wake.set()

    async def start(self, flush: Flush) -> None:
        if self._task is not None:
            return
        self._flush = flush
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="telemetry-batch")
        logger.info("telemetry batch window is %ss, max size is %s", self._window_seconds, self._max_batch_size)

    async def stop(self) -> None:
        self._running = False
        self._wake.set()
        task = self._task
        self._task = None
        if task is not None:
            await task

    async def _loop(self) -> None:
        while self._running:
            if self._limit is not None:
                self._max_batch_size = max(1, await self._limit())
            async with self._lock:
                full = len(self._pending) >= self._max_batch_size
            if full:
                self._wake.set()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), timeout=self._window_seconds)
            self._wake.clear()
            await self._drain()
        await self._drain()

    async def _drain(self) -> None:
        """Cleans up the pending points.
        Start a new task to flush the points.
        """
        async with self._lock:
            items = self._pending
            self._pending = []
        if not items or self._flush is None:
            return
        try:
            await self._flush(items)
        except Exception:
            async with self._lock:
                self._pending = items + self._pending
            logger.exception("failed to flush %s telemetry points", len(items))
