from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.device import Device
from app.db.models.subscription import Polygon, Subscription
from app.db.models.telemetry import Telemetry
from app.db.models.user import User
from app.db.session import get_session_factory


async def delete_emails(emails: list[str]) -> None:
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(delete(User).where(User.email.in_(emails)))
        await session.commit()


async def delete_device_tree(email: str, device_id: int) -> None:
    factory = get_session_factory()
    async with factory() as session:
        await _delete_device(session, device_id)
        await session.execute(delete(User).where(User.email == email))
        await session.commit()


async def delete_devices(emails: tuple[str, str], device_id: int) -> None:
    factory = get_session_factory()
    async with factory() as session:
        await _delete_device(session, device_id)
        await session.execute(delete(User).where(User.email.in_(emails)))
        await session.commit()


async def add_subscription(user_id: int, device_id: int) -> None:
    factory = get_session_factory()
    async with factory() as session:
        polygon = Polygon(polygon="POLYGON((0 0, 1 0, 1 1, 0 0))")
        session.add(polygon)
        await session.flush()
        session.add(Subscription(user_id=user_id, device_id=device_id, polygon_id=polygon.id))
        await session.commit()


async def add_old_point(device_id: int, timestamp: datetime) -> None:
    factory = get_session_factory()
    async with factory() as session:
        session.add(Telemetry(device_id=device_id, location="POINT(1 2)", timestamp=timestamp))
        await session.commit()


async def _delete_device(session: AsyncSession, device_id: int) -> None:
    if not device_id:
        return
    await session.execute(delete(Telemetry).where(Telemetry.device_id == device_id))
    await session.execute(delete(Subscription).where(Subscription.device_id == device_id))
    await session.execute(delete(Device).where(Device.id == device_id))
