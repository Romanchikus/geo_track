import uuid

import pytest
from shapely.wkt import loads
from sqlalchemy import delete

from app.db.models.device import Device
from app.db.models.subscription import Polygon, Subscription
from app.db.models.user import User
from app.db.session import dispose_engine, get_session_factory
from app.services.telemetry.processing.coverage import merged_polygon

pytestmark = pytest.mark.integration

_WEST = "POLYGON((0 0, 2 0, 2 2, 0 2, 0 0))"
_EAST = "POLYGON((10 10, 12 10, 12 12, 10 12, 10 10))"


async def test_union_covers_only_connected_users(migrated: None) -> None:
    factory = get_session_factory()
    west_user = 0
    east_user = 0
    device_id = 0
    polygon_ids: list[int] = []
    try:
        async with factory() as session:
            west = User(email=f"west-{uuid.uuid4().hex}@example.com", password_hash="hash")
            east = User(email=f"east-{uuid.uuid4().hex}@example.com", password_hash="hash")
            device = Device(name="tracker")
            session.add_all([west, east, device])
            await session.commit()
            west_user = west.id
            east_user = east.id
            device_id = device.id

        async with factory() as session:
            west_polygon = Polygon(polygon=_WEST)
            east_polygon = Polygon(polygon=_EAST)
            session.add_all([west_polygon, east_polygon])
            await session.flush()
            session.add(Subscription(user_id=west_user, device_id=device_id, polygon_id=west_polygon.id))
            session.add(Subscription(user_id=east_user, device_id=device_id, polygon_id=east_polygon.id))
            await session.commit()
            polygon_ids = [west_polygon.id, east_polygon.id]

        async with factory() as session:
            west_only = await merged_polygon(session, [west_user])
            both = await merged_polygon(session, [west_user, east_user])
            assert west_only is not None
            assert both is not None
            west_shape = loads(west_only)
            both_shape = loads(both)
            assert west_shape.covers(loads("POINT(1 1)"))
            assert not west_shape.covers(loads("POINT(11 11)"))
            assert both_shape.covers(loads("POINT(1 1)"))
            assert both_shape.covers(loads("POINT(11 11)"))
    finally:
        async with factory() as session:
            if west_user or east_user:
                await session.execute(delete(User).where(User.id.in_([west_user, east_user])))
            if polygon_ids:
                await session.execute(delete(Polygon).where(Polygon.id.in_(polygon_ids)))
            if device_id:
                await session.execute(delete(Device).where(Device.id == device_id))
            await session.commit()
        await dispose_engine()
