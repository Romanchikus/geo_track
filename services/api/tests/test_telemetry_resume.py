from typing import cast

from rstream import Consumer, EventContext, OffsetNotFound, OffsetType
from wire.telemetry_codec import STREAM

from app.services.telemetry.processing.stream import SUBSCRIBER, on_active


class _Consumer:
    def __init__(self, stored: int | None) -> None:
        self._stored = stored

    async def query_offset(self, stream: str, subscriber_name: str) -> int:
        assert stream == STREAM
        assert subscriber_name == SUBSCRIBER
        if self._stored is None:
            raise OffsetNotFound
        return self._stored


def _context(stored: int | None) -> EventContext:
    return EventContext(
        consumer=cast(Consumer, _Consumer(stored)),
        stream=STREAM,
        subscriber_id=1,
        subscriber_name=SUBSCRIBER,
        reference=SUBSCRIBER,
    )


async def test_standby_does_not_read_the_stream() -> None:
    offset = await on_active(False, _context(4))

    assert offset.offset_type is OffsetType.NEXT
    assert offset.offset == 0


async def test_activation_resumes_after_the_committed_offset() -> None:
    offset = await on_active(True, _context(4))

    assert offset.offset_type is OffsetType.OFFSET
    assert offset.offset == 5


async def test_activation_starts_at_the_tail_when_nothing_is_committed() -> None:
    offset = await on_active(True, _context(None))

    assert offset.offset_type is OffsetType.NEXT
    assert offset.offset == 0
