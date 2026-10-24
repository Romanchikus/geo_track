from typing import cast

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.subscriptions import DeviceMode, SubscriptionUpdate
from app.services.subscriptions.selection import devices_for_mode

TRIANGLE = [[30.0, 50.0], [31.0, 50.0], [31.0, 51.0]]


def test_patch_accepts_a_polygon_or_a_device_scope() -> None:
    moved = SubscriptionUpdate.model_validate({"coordinates": TRIANGLE})
    assert moved.coordinates == TRIANGLE
    assert moved.mode is None

    chosen = SubscriptionUpdate.model_validate({"mode": "ids", "device_ids": [4, 9]})
    assert chosen.mode is DeviceMode.ids
    assert chosen.device_ids == [4, 9]

    shared = SubscriptionUpdate.model_validate({"mode": "percent", "percent": 25})
    assert shared.percent == 25

    everyone = SubscriptionUpdate.model_validate({"mode": "all"})
    assert everyone.mode is DeviceMode.all


def test_patch_rejects_an_empty_change() -> None:
    with pytest.raises(ValidationError):
        SubscriptionUpdate.model_validate({})
    with pytest.raises(ValidationError):
        SubscriptionUpdate.model_validate({"mode": "percent"})
    with pytest.raises(ValidationError):
        SubscriptionUpdate.model_validate({"mode": "ids", "device_ids": []})


async def test_patch_percent_uses_the_same_share_as_create(monkeypatch: pytest.MonkeyPatch) -> None:
    async def only_these(_session: object) -> list[int]:
        return [1, 2, 3, 4]

    monkeypatch.setattr("app.services.subscriptions.selection._available_ids", only_these)
    monkeypatch.setattr(
        "app.services.subscriptions.selection.random.sample",
        lambda population, count: list(population)[:count],
    )
    chosen = await devices_for_mode(cast(AsyncSession, None), DeviceMode.percent, 50, [])
    assert chosen == [1, 2]
