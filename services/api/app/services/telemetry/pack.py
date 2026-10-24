import struct

from app.schemas.telemetry import TelemetryPoint

# int64 device id, float32 latitude, float32 longitude, uint32 epoch seconds.
_POINT = struct.Struct("<qffI")


def pack_points(points: list[TelemetryPoint]) -> bytes:
    """Pack points into the little-endian layout the browser unpacks."""
    out = bytearray(len(points) * _POINT.size)
    for index, point in enumerate(points):
        _POINT.pack_into(
            out,
            index * _POINT.size,
            point.device_id,
            point.latitude,
            point.longitude,
            int(point.timestamp.timestamp()),
        )
    return bytes(out)
