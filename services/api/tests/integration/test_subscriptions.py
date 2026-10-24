import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.models.alert import Alert
from app.db.models.device import Device
from app.db.models.subscription import Polygon, Subscription
from app.db.models.user import User
from app.db.session import dispose_engine, get_session_factory

pytestmark = pytest.mark.integration


async def test_subscription_links_user_and_device_and_owns_alerts(migrated: None) -> None:
    factory = get_session_factory()
    user_id = 0
    device_id = 0
    subscription_id = 0
    polygon_id = 0
    try:
        async with factory() as session:
            user = User(email=f"sub-{uuid.uuid4().hex}@example.com", password_hash="hash")
            device = Device(name="tracker")
            session.add_all([user, device])
            await session.commit()
            user_id = user.id
            device_id = device.id

        async with factory() as session:
            polygon = Polygon(polygon="POLYGON((0 0, 1 0, 1 1, 0 0))")
            session.add(polygon)
            await session.flush()
            subscription = Subscription(user_id=user_id, device_id=device_id, polygon_id=polygon.id)
            session.add(subscription)
            await session.commit()
            subscription_id = subscription.id
            polygon_id = polygon.id
            session.add(Alert(subscription_id=subscription_id, message="left zone"))
            await session.commit()

        async with factory() as session:
            other = Polygon(polygon="POLYGON((2 2, 3 2, 3 3, 2 2))")
            session.add(other)
            await session.flush()
            session.add(Subscription(user_id=user_id, device_id=device_id, polygon_id=other.id))
            await session.commit()

        async with factory() as session:
            session.add(Subscription(user_id=user_id, device_id=device_id, polygon_id=polygon_id))
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()

        async with factory() as session:
            loaded_user = await session.get(User, user_id)
            assert loaded_user is not None
            await session.delete(loaded_user)
            await session.commit()
            assert await session.get(Subscription, subscription_id) is None
            remaining = await session.scalar(
                select(func.count()).select_from(Alert).where(Alert.subscription_id == subscription_id)
            )
            assert remaining == 0
    finally:
        try:
            async with factory() as session:
                stored = await session.get(Device, device_id)
                if stored is not None:
                    await session.delete(stored)
                    await session.commit()
        finally:
            await dispose_engine()
