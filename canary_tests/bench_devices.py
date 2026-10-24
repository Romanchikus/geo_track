import argparse
import asyncio
import logging
import os
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import aiomqtt
import httpx
from wire.telemetry_codec import TOPIC, encode

from canary_tests.devices_store import save_device_ids
from canary_tests.pace import Pace, RedisPace
from canary_tests.positions import DEFAULT_SPEED_KMH, Track, positions_for, random_track, save_positions, step_fix
from canary_tests.supply import watch_device_supply

logger = logging.getLogger(__name__)

DEFAULT_DEVICES_FILE = Path(__file__).resolve().parent / "devices.pkl"
DEFAULT_POSITIONS_FILE = Path(__file__).resolve().parent / "positions.pkl"


@dataclass(slots=True)
class Settings:
    base_url: str
    devices: int
    loops: int
    per_second: int
    internal_token: str
    devices_file: Path
    positions_file: Path
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    mqtt_ca: Path
    redis_url: str


@dataclass(slots=True)
class _Cursor:
    index: int = 0
    sent: int = 0


class Publisher(Protocol):
    async def publish(self, topic: str, payload: bytes, qos: int = 0) -> None:
        """Publish one MQTT payload."""


def parse_args() -> Settings:
    parser = argparse.ArgumentParser(
        description=(
            "Load existing devices or create up to 10_000 in one request, save them, "
            "then publish one telemetry event per device per loop over MQTT."
        )
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--devices", type=int, default=10_000)
    parser.add_argument("--loops", type=int, default=0, help="0 runs forever")
    parser.add_argument("--concurrency", type=int, default=10_000, help="telemetry publishes per second")
    parser.add_argument("--internal-token", default=os.environ.get("INTERNAL_TOKEN", "dev-internal-token"))
    parser.add_argument("--devices-file", type=Path, default=DEFAULT_DEVICES_FILE)
    parser.add_argument("--positions-file", type=Path, default=DEFAULT_POSITIONS_FILE)
    parser.add_argument("--mqtt-host", default=os.environ.get("MQTT_HOST", "rabbitmq"))
    parser.add_argument("--mqtt-port", type=int, default=int(os.environ.get("MQTT_PORT", "8883")))
    parser.add_argument("--mqtt-username", default=os.environ.get("MQTT_USERNAME", "geo"))
    parser.add_argument("--mqtt-password", default=os.environ.get("MQTT_PASSWORD", "geo"))
    parser.add_argument("--mqtt-ca", type=Path, default=Path(os.environ.get("MQTT_CA", "/certs/ca.pem")))
    parser.add_argument("--redis-url", default=os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    args = parser.parse_args()
    if args.devices < 1:
        parser.error("--devices must be positive")
    if args.loops < 0:
        parser.error("--loops must be 0 or more")
    if args.concurrency < 1:
        parser.error("--concurrency must be positive")
    if args.mqtt_port < 1:
        parser.error("--mqtt-port must be positive")
    return Settings(
        base_url=args.base_url.rstrip("/"),
        devices=args.devices,
        loops=args.loops,
        per_second=args.concurrency,
        internal_token=args.internal_token,
        devices_file=args.devices_file,
        positions_file=args.positions_file,
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        mqtt_username=args.mqtt_username,
        mqtt_password=args.mqtt_password,
        mqtt_ca=args.mqtt_ca,
        redis_url=args.redis_url,
    )


async def run(settings: Settings) -> None:
    if not settings.internal_token:
        logger.error("INTERNAL_TOKEN is required to create devices")
        raise SystemExit(1)
    if not settings.mqtt_ca.is_file():
        logger.error("MQTT CA file is missing: %s", settings.mqtt_ca)
        raise SystemExit(1)
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(base_url=settings.base_url, timeout=timeout) as http:
        device_ids = await ensure_devices(http, settings)
        rng = random.Random()
        positions = positions_for(device_ids, settings.positions_file, rng)
        total = None if settings.loops == 0 else settings.loops * len(device_ids)
        logger.info("sending up to %s telemetry posts per second on one mqtt connection", settings.per_second)
        cursor = _Cursor()
        pace = RedisPace(settings.redis_url, settings.per_second)
        stop = asyncio.Event()
        supply = asyncio.create_task(
            watch_device_supply(
                device_ids,
                positions,
                settings.devices_file,
                settings.positions_file,
                pace,
                rng,
                stop,
                lambda count: create_device_batch(http, count, settings.internal_token),
            ),
            name="device-supply",
        )
        try:
            while total is None or cursor.sent < total:
                try:
                    async with aiomqtt.Client(
                        settings.mqtt_host,
                        settings.mqtt_port,
                        username=settings.mqtt_username,
                        password=settings.mqtt_password,
                        identifier="canary-telemetry",
                        tls_params=aiomqtt.TLSParameters(ca_certs=str(settings.mqtt_ca)),
                    ) as client:
                        logger.info("mqtt connected to %s:%s", settings.mqtt_host, settings.mqtt_port)
                        await send_telemetry(
                            client,
                            device_ids,
                            settings.per_second,
                            total,
                            cursor,
                            positions,
                            settings.positions_file,
                            rng,
                            pace,
                        )
                except Exception:
                    logger.exception("mqtt publish failed")
                    await asyncio.sleep(1)
        finally:
            stop.set()
            await supply
            await pace.close()


async def ensure_devices(client: httpx.AsyncClient, settings: Settings) -> list[int]:
    device_ids = await fetch_device_ids(client, settings.internal_token)
    missing = settings.devices - len(device_ids)
    if missing > 0:
        batch = min(missing, 10_000)
        logger.info("POST /devices/batch for %s devices", batch)
        started = time.perf_counter()
        device_ids.extend(await create_device_batch(client, batch, settings.internal_token))
        elapsed = time.perf_counter() - started
        logger.info("POST /devices/batch created %s in %.3fs", batch, elapsed)
    device_ids = device_ids[: settings.devices]
    save_device_ids(settings.devices_file, device_ids)
    return device_ids


async def fetch_device_ids(client: httpx.AsyncClient, internal_token: str) -> list[int]:
    response = await client.get("/devices/all", headers={"X-Internal-Token": internal_token})
    if response.status_code != 200:
        logger.error("GET /devices/all failed: %s", response.status_code)
        raise SystemExit(1)
    return _device_ids(response.json())


async def create_device_batch(client: httpx.AsyncClient, count: int, internal_token: str) -> list[int]:
    response = await client.post(
        "/devices/batch",
        json={"count": count},
        headers={"X-Internal-Token": internal_token},
        timeout=120.0,
    )
    if response.status_code != 201:
        logger.error("POST /devices/batch failed: %s", response.status_code)
        raise SystemExit(1)
    return _device_ids(response.json())


class _FixedPace:
    def __init__(self, points_per_second: int) -> None:
        self._rate = points_per_second

    async def read(self) -> tuple[float, int]:
        return DEFAULT_SPEED_KMH, self._rate


async def send_telemetry(
    client: Publisher,
    device_ids: list[int],
    per_second: int,
    total: int | None,
    cursor: _Cursor,
    positions: dict[int, Track],
    positions_file: Path,
    rng: random.Random,
    pace: Pace | None = None,
) -> None:
    """Publish up to the current pace of protobuf fixes each second. Do not wait for a reply."""
    if not device_ids:
        return
    source = _FixedPace(per_second) if pace is None else pace
    while total is None or cursor.sent < total:
        started = time.perf_counter()
        speed_kmh, rate = await source.read()
        budget = rate if total is None else min(rate, total - cursor.sent)
        delivered = 0
        for _ in range(budget):
            device_id = device_ids[cursor.index % len(device_ids)]
            track = _current_track(positions, device_id, rng)
            payload = encode(device_id, track.latitude, track.longitude, datetime.now(UTC))
            await client.publish(TOPIC, payload, qos=0)
            positions[device_id] = step_fix(track, speed_kmh)
            cursor.index += 1
            delivered += 1
        save_positions(positions_file, positions)
        logger.info("canary sent %s", delivered)
        cursor.sent += delivered
        if total is not None and cursor.sent >= total:
            return
        remaining = 1.0 - (time.perf_counter() - started)
        if remaining > 0:
            await asyncio.sleep(remaining)


def _current_track(positions: dict[int, Track], device_id: int, rng: random.Random) -> Track:
    found = positions.get(device_id)
    if found is not None:
        return found
    logger.info("device %s had no stored position; placing it at random", device_id)
    return random_track(rng)


def _device_ids(payload: object) -> list[int]:
    if not isinstance(payload, list):
        raise RuntimeError("device response was not a list")
    device_ids: list[int] = []
    for item in payload:
        if not isinstance(item, dict):
            raise RuntimeError("device response was not an object")
        device_id = item.get("id")
        if not isinstance(device_id, int) or isinstance(device_id, bool):
            raise RuntimeError("device response missing id")
        device_ids.append(device_id)
    return device_ids


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        asyncio.run(run(parse_args()))
    except KeyboardInterrupt:
        logger.info("stopped")


if __name__ == "__main__":
    main()
