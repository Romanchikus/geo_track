import logging

from fastapi import HTTPException, status
from geoalchemy2.elements import WKBElement, WKTElement
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.subscription import Polygon, Subscription
from app.schemas.subscriptions import (
    DeviceMode,
    SubscriptionArea,
    SubscriptionCreate,
    SubscriptionDevice,
    SubscriptionUpdate,
)
from app.services.subscriptions.geometry import normalize_ring, read_ring, stored_polygon, to_wkt
from app.services.subscriptions.selection import choose_device_ids, devices_for_mode, require_devices
from app.services.telemetry.processing.sockets import websocket_manager

logger = logging.getLogger(__name__)


async def create_subscription(session: AsyncSession, user_id: int, body: SubscriptionCreate) -> SubscriptionArea:
    ring = normalize_ring(body.coordinates)
    device_ids = await choose_device_ids(session, body)
    polygon = Polygon(polygon=stored_polygon(session, to_wkt(ring)))
    session.add(polygon)
    await session.flush()
    subscriptions = [
        Subscription(user_id=user_id, device_id=device_id, polygon_id=polygon.id) for device_id in device_ids
    ]
    session.add_all(subscriptions)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        logger.info("create subscription rejected for user %s", user_id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Device already subscribed") from None
    await websocket_manager.refresh()
    logger.info("created subscription polygon %s user %s devices %s", polygon.id, user_id, len(subscriptions))
    return _area(polygon.id, ring, subscriptions)


async def list_subscriptions(
    session: AsyncSession,
    user_id: int,
    limit: int,
    offset: int,
) -> list[SubscriptionArea]:
    polygon_ids = list(
        await session.scalars(
            select(Polygon.id)
            .join(Subscription, Subscription.polygon_id == Polygon.id)
            .where(Subscription.user_id == user_id)
            .distinct()
            .order_by(Polygon.id)
            .limit(limit)
            .offset(offset)
        )
    )
    if not polygon_ids:
        return []
    return await _areas_for(session, user_id, polygon_ids)


async def get_subscription(session: AsyncSession, user_id: int, polygon_id: int) -> SubscriptionArea:
    areas = await _areas_for(session, user_id, [polygon_id])
    if not areas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return areas[0]


async def update_subscription(
    session: AsyncSession,
    user_id: int,
    polygon_id: int,
    body: SubscriptionUpdate,
) -> SubscriptionArea:
    polygon = await require_polygon(session, user_id, polygon_id)
    coordinates = body.coordinates
    if coordinates is not None:
        ring = normalize_ring(coordinates)
        polygon.polygon = stored_polygon(session, to_wkt(ring))
    if body.mode is not None or body.device_ids is not None:
        mode = body.mode or DeviceMode.ids
        device_ids = await devices_for_mode(session, mode, body.percent, body.device_ids or [])
        await _replace_devices(session, user_id, polygon_id, device_ids)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        logger.info("update subscription rejected polygon %s user %s", polygon_id, user_id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Device already subscribed") from None
    await websocket_manager.refresh()
    logger.info("updated subscription polygon %s user %s", polygon_id, user_id)
    return await get_subscription(session, user_id, polygon_id)


async def delete_subscription(session: AsyncSession, user_id: int, polygon_id: int) -> None:
    await get_subscription(session, user_id, polygon_id)
    polygon = await session.get(Polygon, polygon_id)
    if polygon is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    await session.delete(polygon)
    await session.commit()
    await websocket_manager.refresh()
    logger.info("deleted subscription polygon %s user %s", polygon_id, user_id)


async def require_polygon(session: AsyncSession, user_id: int, polygon_id: int) -> Polygon:
    """Return the polygon when this user has a subscription on it."""
    polygon = await session.scalar(
        select(Polygon)
        .join(Subscription, Subscription.polygon_id == Polygon.id)
        .where(Subscription.user_id == user_id, Polygon.id == polygon_id)
        .limit(1)
    )
    if polygon is None:
        logger.info("subscription polygon %s not found for user %s", polygon_id, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return polygon


async def _replace_devices(session: AsyncSession, user_id: int, polygon_id: int, device_ids: list[int]) -> None:
    wanted = await require_devices(session, device_ids)
    current = list(
        await session.scalars(
            select(Subscription).where(Subscription.polygon_id == polygon_id, Subscription.user_id == user_id)
        )
    )
    current_ids = {row.device_id for row in current}
    for row in current:
        if row.device_id not in wanted:
            await session.delete(row)
    for device_id in wanted:
        if device_id not in current_ids:
            session.add(Subscription(user_id=user_id, device_id=device_id, polygon_id=polygon_id))


async def _areas_for(session: AsyncSession, user_id: int, polygon_ids: list[int]) -> list[SubscriptionArea]:
    rows = (
        await session.execute(
            select(Subscription, Polygon.polygon)
            .join(Polygon, Polygon.id == Subscription.polygon_id)
            .where(Subscription.user_id == user_id, Polygon.id.in_(polygon_ids))
            .order_by(Polygon.id, Subscription.id)
        )
    ).all()
    grouped: dict[int, tuple[WKBElement | WKTElement | str, list[Subscription]]] = {}
    for subscription, polygon_value in rows:
        bucket = grouped.get(subscription.polygon_id)
        if bucket is None:
            grouped[subscription.polygon_id] = (polygon_value, [subscription])
            continue
        bucket[1].append(subscription)
    return [
        _area(polygon_id, read_ring(polygon_value), subscriptions)
        for polygon_id, (polygon_value, subscriptions) in grouped.items()
    ]


def _area(
    polygon_id: int,
    ring: list[list[float]],
    subscriptions: list[Subscription],
) -> SubscriptionArea:
    return SubscriptionArea(
        polygon_id=polygon_id,
        coordinates=ring,
        devices=[SubscriptionDevice(subscription_id=row.id, device_id=row.device_id) for row in subscriptions],
    )
