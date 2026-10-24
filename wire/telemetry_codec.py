from dataclasses import dataclass
from datetime import UTC, datetime

from google.protobuf.message import DecodeError

from wire import telemetry_pb2

TOPIC = "telemetry"
STREAM = "telemetry"
_SCALE = 10_000_000


@dataclass(slots=True, frozen=True)
class Telemetry:
    device_id: int
    latitude: float
    longitude: float
    timestamp: datetime


def encode(device_id: int, latitude: float, longitude: float, timestamp: datetime) -> bytes:
    """Encode one fix with the compiled protobuf runtime."""
    moment = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=UTC)
    message = telemetry_pb2.Telemetry(
        device_id=device_id,
        latitude_e7=round(latitude * _SCALE),
        longitude_e7=round(longitude * _SCALE),
        timestamp_ms=int(moment.timestamp() * 1000),
    )
    return message.SerializeToString()


def decode(payload: bytes) -> Telemetry:
    """Decode one fix with the compiled protobuf runtime."""
    message = telemetry_pb2.Telemetry()
    try:
        _ = message.ParseFromString(payload)
    except DecodeError as exc:
        raise ValueError("telemetry payload is invalid") from exc
    if message.device_id <= 0 or not message.HasField("timestamp_ms"):
        raise ValueError("telemetry payload is missing device_id or timestamp")
    return Telemetry(
        device_id=message.device_id,
        latitude=message.latitude_e7 / _SCALE,
        longitude=message.longitude_e7 / _SCALE,
        timestamp=datetime.fromtimestamp(message.timestamp_ms / 1000, UTC),
    )
