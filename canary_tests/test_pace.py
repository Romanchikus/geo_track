from canary_tests.pace import RedisPace, next_pace
from canary_tests.positions import Track, step_fix


def test_next_pace_keeps_the_previous_speed() -> None:
    assert next_pace("250", 10.0) == 250.0
    assert next_pace(None, 10.0) == 10.0
    assert next_pace("fast", 10.0) == 10.0
    assert next_pace("-5", 10.0) == 10.0


def test_step_uses_the_given_speed() -> None:
    start = Track(0.0, 0.0, 90.0)
    slow = step_fix(start, speed_kmh=3600.0)
    fast = step_fix(start, speed_kmh=36_000.0)

    assert slow.longitude > start.longitude
    assert fast.longitude > slow.longitude


class _Redis:
    def __init__(self) -> None:
        self.values = {"load:speed_kmh": "180"}
        self.closed = False

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def aclose(self) -> None:
        self.closed = True


class _Down:
    def __init__(self) -> None:
        self.closed = False

    async def get(self, key: str) -> str | None:
        raise ConnectionError("down")

    async def aclose(self) -> None:
        self.closed = True


async def test_redis_pace_reads_speed_and_keeps_the_rate() -> None:
    redis = _Redis()
    pace = RedisPace("redis://unused", 10, client=redis)

    assert await pace.read() == (180.0, 10)
    redis.values.clear()
    assert await pace.read() == (180.0, 10)


async def test_redis_pace_keeps_the_last_pace_when_redis_fails() -> None:
    redis = _Down()
    pace = RedisPace("redis://unused", 12, client=redis)

    assert await pace.read() == (50_000.0, 12)
    assert redis.closed is True
