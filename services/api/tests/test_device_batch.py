import pytest
from pydantic import ValidationError

from app.schemas.devices import DeviceBatchCreate


def test_device_batch_accepts_up_to_10_000() -> None:
    assert DeviceBatchCreate(count=10_000).count == 10_000


def test_device_batch_rejects_more_than_10_000() -> None:
    with pytest.raises(ValidationError):
        DeviceBatchCreate(count=10_001)
