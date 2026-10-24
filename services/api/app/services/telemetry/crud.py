from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from fastapi_filters import SortingValues
from fastapi_filters.ext.sqlalchemy import apply_filters_and_sorting
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.telemetry import Telemetry
from app.schemas.telemetry import TelemetryFilters


def _sqlite(session: AsyncSession) -> bool:
    return session.get_bind().dialect.name == "sqlite"


def _points(session: AsyncSession) -> Any:
    if _sqlite(session):
        return select(Telemetry.device_id, Telemetry.location, Telemetry.timestamp)
    return select(
        Telemetry.device_id,
        ST_Y(cast(Telemetry.location, Geometry)).label("latitude"),
        ST_X(cast(Telemetry.location, Geometry)).label("longitude"),
        Telemetry.timestamp,
    )


def _rows(session: AsyncSession, rows: Any) -> list[dict[str, object]]:
    if not _sqlite(session):
        return [dict(row) for row in rows]
    parsed: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        longitude, latitude = _parse_point(str(item.pop("location")))
        item["longitude"] = longitude
        item["latitude"] = latitude
        parsed.append(item)
    return parsed


def _parse_point(value: str) -> tuple[float, float]:
    inner = value.removeprefix("POINT(").removesuffix(")")
    longitude, latitude = inner.split()
    return float(longitude), float(latitude)


async def list_telemetry(
    session: AsyncSession,
    filters: TelemetryFilters,
    sorting: SortingValues,
    limit: int,
    offset: int,
) -> list[dict[str, object]]:
    stmt = apply_filters_and_sorting(_points(session), filters, sorting)
    rows = await session.execute(stmt.limit(limit).offset(offset))
    return _rows(session, rows.mappings())


async def get_telemetry(
    session: AsyncSession,
    device_id: int,
    timestamp: datetime,
) -> dict[str, object]:
    stmt = _points(session).where(
        Telemetry.device_id == device_id,
        Telemetry.timestamp == timestamp,
    )
    row = (await session.execute(stmt)).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telemetry not found")
    return _rows(session, [row])[0]
