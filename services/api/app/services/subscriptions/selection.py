import random

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.device import Device
from app.schemas.subscriptions import DeviceMode, SubscriptionCreate


def select_count(total: int, percent: int) -> int:
    """How many devices a percent mode keeps. A non-zero percent keeps at least one."""
    if total <= 0 or percent <= 0:
        return 0
    if percent >= 100:
        return total
    return max(1, (total * percent) // 100)


async def choose_device_ids(session: AsyncSession, body: SubscriptionCreate) -> list[int]:
    return await devices_for_mode(session, body.mode, body.percent, body.device_ids)


async def devices_for_mode(
    session: AsyncSession,
    mode: DeviceMode,
    percent: int | None,
    device_ids: list[int],
) -> list[int]:
    """Resolve all, percent, or explicit device ids into the subscription's device list."""
    if mode is DeviceMode.ids:
        return await require_devices(session, device_ids)
    available = await _available_ids(session)
    if not available:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No devices to subscribe")
    if mode is DeviceMode.all or percent == 100:
        return available
    assert percent is not None
    picked = random.sample(available, select_count(len(available), percent))
    picked.sort()
    return picked


async def require_devices(session: AsyncSession, device_ids: list[int]) -> list[int]:
    """Return unique device ids that exist. A device may belong to many areas."""
    wanted = list(dict.fromkeys(device_ids))
    found = set(await session.scalars(select(Device.id).where(Device.id.in_(wanted))))
    if any(device_id not in found for device_id in wanted):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return wanted


async def _available_ids(session: AsyncSession) -> list[int]:
    return list(await session.scalars(select(Device.id).order_by(Device.id)))
