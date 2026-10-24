from datetime import UTC, datetime

import pytest
from wire.telemetry_codec import decode, encode

from app.services.telemetry.processing.broker import message_body, point_from_payload


def test_telemetry_protobuf_round_trip() -> None:
    stamp = datetime(2026, 10, 23, 9, 0, tzinfo=UTC)
    payload = encode(7, 55.75, 37.61, stamp)

    point = point_from_payload(payload)

    assert len(payload) < 32
    assert point.device_id == 7
    assert point.latitude == pytest.approx(55.75)
    assert point.longitude == pytest.approx(37.61)
    assert point.timestamp == stamp
    assert decode(message_body([payload])) == decode(payload)


def test_telemetry_protobuf_rejects_a_short_payload() -> None:
    with pytest.raises(ValueError):
        decode(b"\x08\x01")
