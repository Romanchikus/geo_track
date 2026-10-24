import random
from pathlib import Path

from canary_tests.devices_store import load_device_ids
from canary_tests.positions import load_positions
from canary_tests.supply import fill_devices


async def test_fill_adds_only_the_missing_devices(tmp_path: Path) -> None:
    device_ids = [1, 2, 3]
    positions = {}
    created: list[int] = []

    async def create_batch(count: int) -> list[int]:
        created.append(count)
        start = 10 + sum(created[:-1])
        return list(range(start, start + count))

    added = await fill_devices(
        device_ids,
        5,
        positions,
        tmp_path / "devices.pkl",
        tmp_path / "positions.pkl",
        random.Random(1),
        create_batch,
    )

    assert added == 2
    assert created == [2]
    assert device_ids == [1, 2, 3, 10, 11]
    assert set(positions) == {10, 11}
    assert load_device_ids(tmp_path / "devices.pkl") == [1, 2, 3, 10, 11]
    assert set(load_positions(tmp_path / "positions.pkl")) == {10, 11}


async def test_fill_splits_a_large_difference_into_batches(tmp_path: Path) -> None:
    device_ids: list[int] = []
    counts: list[int] = []
    nxt = 1

    async def create_batch(count: int) -> list[int]:
        nonlocal nxt
        counts.append(count)
        ids = list(range(nxt, nxt + count))
        nxt += count
        return ids

    added = await fill_devices(
        device_ids,
        12_000,
        {},
        tmp_path / "devices.pkl",
        tmp_path / "positions.pkl",
        random.Random(2),
        create_batch,
    )

    assert added == 12_000
    assert counts == [10_000, 2_000]
    assert len(device_ids) == 12_000


async def test_fill_leaves_extra_devices_in_place(tmp_path: Path) -> None:
    device_ids = [4, 5, 6]

    async def create_batch(count: int) -> list[int]:
        raise AssertionError(count)

    added = await fill_devices(
        device_ids,
        2,
        {},
        tmp_path / "devices.pkl",
        tmp_path / "positions.pkl",
        random.Random(3),
        create_batch,
    )

    assert added == 0
    assert device_ids == [4, 5, 6]
    assert not (tmp_path / "devices.pkl").exists()
