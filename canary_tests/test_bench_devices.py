import random
from pathlib import Path

import pytest
from wire.telemetry_codec import TOPIC, decode

from canary_tests.bench_devices import _Cursor, send_telemetry
from canary_tests.positions import Track, load_positions, step_fix


class _Pace:
    def __init__(self, speed_kmh: float, points_per_second: int) -> None:
        self.speed_kmh = speed_kmh
        self.points_per_second = points_per_second

    async def read(self) -> tuple[float, int]:
        return self.speed_kmh, self.points_per_second


class _Client:
    def __init__(self) -> None:
        self.topics: list[str] = []
        self.payloads: list[bytes] = []

    async def publish(self, topic: str, payload: bytes, qos: int = 0) -> None:
        assert qos == 0
        self.topics.append(topic)
        self.payloads.append(payload)


async def test_send_telemetry_publishes_stored_coordinates_then_steps(tmp_path: Path) -> None:
    client = _Client()
    path = tmp_path / "positions.pkl"
    positions = {
        7: Track(1.0, 2.0, 10.0),
        8: Track(3.0, 4.0, 80.0),
        9: Track(5.0, 6.0, 160.0),
        10: Track(7.0, 8.0, 250.0),
    }
    expected_next = {device_id: step_fix(track) for device_id, track in positions.items()}

    await send_telemetry(client, [7, 8, 9, 10], 4, 4, _Cursor(), positions, path, random.Random(5))

    assert client.topics == [TOPIC, TOPIC, TOPIC, TOPIC]
    points = [decode(payload) for payload in client.payloads]
    assert [point.device_id for point in points] == [7, 8, 9, 10]
    assert points[0].latitude == pytest.approx(1.0)
    assert points[0].longitude == pytest.approx(2.0)
    assert points[0].timestamp.tzinfo is not None
    assert load_positions(path) == expected_next


async def test_send_telemetry_uses_the_live_pace(tmp_path: Path) -> None:
    client = _Client()
    path = tmp_path / "positions.pkl"
    positions = {7: Track(0.0, 0.0, 90.0), 8: Track(1.0, 2.0, 0.0)}
    pace = _Pace(3600.0, 1)

    await send_telemetry(client, [7, 8], 4, 1, _Cursor(), positions, path, random.Random(1), pace)

    stored = load_positions(path)

    assert len(client.payloads) == 1
    assert stored[7] == step_fix(Track(0.0, 0.0, 90.0), 3600.0)
    assert stored[8] == Track(1.0, 2.0, 0.0)
