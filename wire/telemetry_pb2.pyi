from google.protobuf.message import Message

class Telemetry(Message):
    device_id: int
    latitude_e7: int
    longitude_e7: int
    timestamp_ms: int

    def __init__(
        self,
        *,
        device_id: int | None = ...,
        latitude_e7: int | None = ...,
        longitude_e7: int | None = ...,
        timestamp_ms: int | None = ...,
    ) -> None: ...
