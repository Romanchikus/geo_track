import pytest

from app.services.telemetry.rate import record_stored, stored_last_second, stored_total


class _Pipe:
    def __init__(self, redis: "_Redis") -> None:
        self._redis = redis
        self._ops: list[tuple[str, str, int]] = []

    async def __aenter__(self) -> "_Pipe":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    def incrby(self, key: str, amount: int) -> None:
        self._ops.append(("incrby", key, amount))

    def expire(self, key: str, seconds: int) -> None:
        self._ops.append(("expire", key, seconds))

    async def execute(self) -> None:
        for kind, key, amount in self._ops:
            if kind == "incrby":
                current = int(self._redis.values.get(key, "0"))
                self._redis.values[key] = str(current + amount)
            else:
                self._redis.ttl[key] = amount


class _Redis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttl: dict[str, int] = {}

    def pipeline(self, transaction: bool = True) -> _Pipe:
        del transaction
        return _Pipe(self)

    async def get(self, key: str) -> str | None:
        return self.values.get(key)


async def test_stored_rate_keeps_the_previous_second(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = _Redis()
    monkeypatch.setattr("app.services.telemetry.rate.get_redis", lambda: redis)

    await record_stored(3, 100.2)
    await record_stored(2, 100.8)
    await record_stored(4, 101.1)

    assert redis.ttl["telemetry:stored:100"] == 3
    assert await stored_last_second(101.0) == 5
    assert await stored_last_second(102.0) == 4
    assert await stored_total() == 9
