import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.device import Device

logger = logging.getLogger(__name__)


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name is required")
    return cleaned


async def create_device(session: AsyncSession, name: str) -> Device:
    device = Device(name=_clean_name(name))
    session.add(device)
    await session.commit()
    logger.info("created device %s", device.id)
    return device


async def create_device_batch(session: AsyncSession, count: int) -> list[Device]:
    devices = [Device(name=f"canary-{index}") for index in range(count)]
    session.add_all(devices)
    await session.commit()
    logger.info("created %s devices", count)
    return devices


async def get_device(session: AsyncSession, device_id: int) -> Device:
    device = await session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


async def list_devices(session: AsyncSession, limit: int, offset: int) -> list[Device]:
    stmt = select(Device).order_by(Device.id).limit(limit).offset(offset)
    result = await session.scalars(stmt)
    return list(result.all())


async def list_all_devices(session: AsyncSession) -> list[Device]:
    result = await session.scalars(select(Device).order_by(Device.id))
    return list(result.all())


async def update_device(session: AsyncSession, device_id: int, name: str) -> Device:
    device = await get_device(session, device_id)
    device.name = _clean_name(name)
    await session.commit()
    logger.info("updated device %s", device.id)
    return device


async def delete_device(session: AsyncSession, device_id: int) -> None:
    device = await get_device(session, device_id)
    try:
        await session.delete(device)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        logger.info("delete device rejected; device %s still has telemetry", device_id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Device has telemetry") from None
    logger.info("deleted device %s", device_id)
