from dataclasses import dataclass
from datetime import datetime

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement, WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.wkt import loads
from sqlalchemy import cast, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.db.models.subscription import Polygon, Subscription
from app.db.models.telemetry import Telemetry
from app.db.session import get_session_factory


@dataclass(slots=True)
class Arrival:
    user_id: int
    device_id: int
    polygon_id: int


@dataclass(slots=True)
class Fix:
    user_id: int
    device_id: int
    polygon_id: int
    timestamp: datetime
    inside: bool


Occupancy = dict[tuple[int, int, int], datetime]


async def coverage_for(user_ids: list[int]) -> str | None:
    """Union the subscription polygons of these users."""
    if not user_ids:
        return None
    factory = get_session_factory()
    async with factory() as session:
        return await merged_polygon(session, user_ids)


async def fixes_for(user_ids: list[int], since: datetime) -> list[Fix]:
    """Return the newest fix for each subscription that still has a point since `since`."""
    if not user_ids:
        return []
    factory = get_session_factory()
    async with factory() as session:
        rows = (await session.execute(_postgres_fixes(user_ids, since))).mappings()
    return [
        _fix(
            int(row["user_id"]),
            int(row["device_id"]),
            int(row["polygon_id"]),
            row["fix_time"],
            bool(row["inside"]),
        )
        for row in rows
    ]


def _postgres_fixes(user_ids: list[int], since: datetime) -> Select[tuple[int, int, int, datetime, bool]]:
    latest = (
        select(
            Telemetry.location.label("location"),
            Telemetry.timestamp.label("fix_time"),
        )
        .where(Telemetry.device_id == Subscription.device_id, Telemetry.timestamp >= since)
        .order_by(Telemetry.timestamp.desc())
        .limit(1)
        .lateral("latest_fix")
    )
    covered = func.ST_Covers(Polygon.polygon, latest.c.location)
    return (
        select(
            Subscription.user_id.label("user_id"),
            Subscription.device_id.label("device_id"),
            Subscription.polygon_id.label("polygon_id"),
            latest.c.fix_time.label("fix_time"),
            covered.label("inside"),
        )
        .select_from(Subscription)
        .join(Polygon, Polygon.id == Subscription.polygon_id)
        .join(latest, true())
        .where(Subscription.user_id.in_(user_ids))
    )


def hold_occupancy(
    held: Occupancy,
    fixes: list[Fix],
    stale_before: datetime,
    user_ids: set[int],
) -> Occupancy:
    """Keep a device in an area until a newer fix is outside it or the stored fix is stale.

    A second with no point does not remove the device. Only a newer point outside the
    polygon, or a fix older than `stale_before`, does.
    """
    state = {key: seen for key, seen in held.items() if key[0] in user_ids and seen >= stale_before}
    for fix in sorted(fixes, key=lambda item: item.timestamp):
        if fix.user_id not in user_ids or fix.timestamp < stale_before:
            continue
        key = (fix.user_id, fix.device_id, fix.polygon_id)
        previous = state.get(key)
        if previous is not None and fix.timestamp < previous:
            continue
        if fix.inside:
            state[key] = fix.timestamp
        elif previous is not None:
            del state[key]
    return state


def arrivals_from(occupancy: Occupancy) -> list[Arrival]:
    return [Arrival(user_id, device_id, polygon_id) for user_id, device_id, polygon_id in sorted(occupancy)]


async def merged_polygon(session: AsyncSession, user_ids: list[int]) -> str | None:
    """Return the WKT union of subscription polygons for these users.

    PostgreSQL unions the geography values on the spheroid.
    """
    if not user_ids:
        return None
    if session.get_bind().dialect.name == "postgresql":
        value = await session.scalar(_postgres_union(user_ids))
        if value is None:
            return None
        return str(value)
    shapes = await _stored_shapes(session, user_ids)
    if not shapes:
        return None
    merged = unary_union(shapes)
    if merged.is_empty:
        return None
    return str(merged.wkt)


def _postgres_union(user_ids: list[int]) -> Select[tuple[object]]:
    polygon_ids = select(Subscription.polygon_id).where(Subscription.user_id.in_(user_ids)).distinct()
    collected = func.ST_Collect(cast(Polygon.polygon, Geometry(srid=4326)))
    merged = func.ST_AsText(func.ST_UnaryUnion(collected))
    return select(merged).where(Polygon.id.in_(polygon_ids))


def _fix(user_id: int, device_id: int, polygon_id: int, timestamp: object, inside: bool) -> Fix:
    if not isinstance(timestamp, datetime):
        raise TypeError("telemetry timestamp was not a datetime")
    return Fix(user_id, device_id, polygon_id, timestamp, inside)


async def _stored_shapes(session: AsyncSession, user_ids: list[int]) -> list[BaseGeometry]:
    stmt = (
        select(Polygon.polygon)
        .join(Subscription, Subscription.polygon_id == Polygon.id)
        .where(Subscription.user_id.in_(user_ids))
    )
    return [_shape(value) for value in (await session.scalars(stmt)).all()]


def _shape(value: object) -> BaseGeometry:
    if isinstance(value, str):
        return loads(value)
    if isinstance(value, (WKBElement, WKTElement)):
        return to_shape(value)
    raise TypeError("stored polygon was not geometry")
