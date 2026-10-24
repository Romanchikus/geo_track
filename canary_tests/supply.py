import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from pathlib import Path

from canary_tests.devices_store import save_device_ids
from canary_tests.pace import Pace
from canary_tests.positions import Track, random_track, save_positions

logger = logging.getLogger(__name__)

_BATCH_LIMIT = 10_000
CreateBatch = Callable[[int], Awaitable[list[int]]]


async def watch_device_supply(
    device_ids: list[int],
    positions: dict[int, Track],
    devices_file: Path,
    positions_file: Path,
    pace: Pace,
    rng: random.Random,
    stop: asyncio.Event,
    create_batch: CreateBatch,
) -> None:
    """When the publish rate rises, create the missing devices in their own task."""
    while not stop.is_set():
        try:
            _speed, rate = await pace.read()
            await fill_devices(device_ids, rate, positions, devices_file, positions_file, rng, create_batch)
        except (Exception, SystemExit):
            logger.exception("device supply failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=1)
        except TimeoutError:
            continue


async def fill_devices(
    device_ids: list[int],
    wanted: int,
    positions: dict[int, Track],
    devices_file: Path,
    positions_file: Path,
    rng: random.Random,
    create_batch: CreateBatch,
) -> int:
    """Create only the devices still missing for this publish rate."""
    added = 0
    while len(device_ids) < wanted:
        count = min(wanted - len(device_ids), _BATCH_LIMIT)
        created = await create_batch(count)
        if len(created) != count:
            logger.error("device batch returned %s ids, wanted %s", len(created), count)
            break
        for device_id in created:
            positions[device_id] = random_track(rng)
        device_ids.extend(created)
        added += len(created)
    if added:
        save_device_ids(devices_file, device_ids)
        save_positions(positions_file, positions)
        logger.info("added %s devices so %s points/s each have a device", added, wanted)
    return added
