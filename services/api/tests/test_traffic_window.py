import pytest

from app.services.traffic import WINDOW_SECONDS, SecondTotal, record_requests, requests_last_second


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
        for kind, key, seconds in self._ops:
            if kind == "incrby":
                current = int(self._redis.values.get(key, "0"))
                self._redis.values[key] = str(current + seconds)
            else:
                self._redis.ttl[key] = seconds


class _Redis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttl: dict[str, int] = {}

    def pipeline(self, transaction: bool = True) -> _Pipe:
        del transaction
        return _Pipe(self)

    async def get(self, key: str) -> str | None:
        return self.values.get(key)


async def test_request_window_keeps_three_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = _Redis()
    monkeypatch.setattr("app.services.traffic.get_redis", lambda: redis)

    await record_requests(1, 100.2)
    await record_requests(1, 100.8)
    await record_requests(1, 101.1)

    assert redis.ttl["http:requests:100"] == WINDOW_SECONDS
    assert redis.values["http:requests:100"] == "2"
    assert redis.values["http:requests:101"] == "1"
    assert await requests_last_second(102.0) == 1


def test_second_total_reports_once_per_second() -> None:
    window = SecondTotal()

    assert window.add(3, 0.4) is None
    assert window.add(2, 0.4) is None
    assert window.add(1, 0.3) == 6
    assert window.add(4, 0.2) is None
