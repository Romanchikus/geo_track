import pytest


@pytest.fixture(autouse=True)
def quiet_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THROUGHPUT_PLUG", "false")

    async def stop_counter() -> None:
        return None

    monkeypatch.setattr("app.main.start_request_counter", lambda: None)
    monkeypatch.setattr("app.main.stop_request_counter", stop_counter)
