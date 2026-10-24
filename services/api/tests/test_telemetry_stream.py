import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app


def test_telemetry_stream_requires_a_session() -> None:
    with TestClient(create_app()) as client:
        disconnected = _read_live(client)

    assert disconnected.code == 4401


def _read_live(client: TestClient) -> WebSocketDisconnect:
    with pytest.raises(WebSocketDisconnect) as caught:
        _receive_live(client)
    return caught.value


def _receive_live(client: TestClient) -> None:
    with client.websocket_connect("/telemetry/live") as websocket:
        websocket.receive_text()
