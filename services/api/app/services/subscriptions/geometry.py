import logging

from fastapi import HTTPException, status
from geoalchemy2.elements import WKBElement, WKTElement
from geoalchemy2.shape import to_shape
from shapely import make_valid
from shapely.geometry import Polygon as ShapePolygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.wkt import loads
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def normalize_ring(coordinates: list[list[float]]) -> list[list[float]]:
    """Return an open lon/lat ring, or reject a ring that is not a polygon."""
    ring = _clean(coordinates)
    shape = ShapePolygon([*ring, ring[0]])
    if shape.is_valid and shape.area > 0:
        return ring
    repaired = _union_ring(shape)
    if not repaired:
        logger.info("rejected subscription ring with %s points", len(ring))
        raise _invalid("Polygon is invalid")
    logger.info("unioned a self-crossing subscription ring from %s points to %s", len(ring), len(repaired))
    return repaired


def _clean(coordinates: list[list[float]]) -> list[list[float]]:
    ring: list[list[float]] = []
    for pair in coordinates:
        if len(pair) < 2:
            raise _invalid("Each coordinate needs longitude and latitude")
        lon = round(float(pair[0]), 6)
        lat = round(float(pair[1]), 6)
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise _invalid("Coordinates are out of range")
        if ring and ring[-1] == [lon, lat]:
            continue
        ring.append([lon, lat])
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(ring) < 3:
        raise _invalid("Polygon needs at least 3 points")
    return ring


def _union_ring(shape: ShapePolygon) -> list[list[float]] | None:
    """Fill a stroke that crosses itself into one solid outer ring."""
    parts = _polygons(make_valid(shape))
    if not parts:
        return None
    filled = unary_union([ShapePolygon(part.exterior) for part in parts if part.area > 0])
    polygons = [part for part in _polygons(filled) if part.area > 0]
    if not polygons:
        return None
    chosen = max(polygons, key=lambda part: part.area)
    return _exterior(chosen) or None


def _polygons(geometry: BaseGeometry) -> list[ShapePolygon]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, ShapePolygon):
        return [geometry]
    if geometry.geom_type in {"MultiPolygon", "GeometryCollection"}:
        found: list[ShapePolygon] = []
        for part in geometry.geoms:
            found.extend(_polygons(part))
        return found
    return []


def _exterior(polygon: ShapePolygon) -> list[list[float]]:
    ring: list[list[float]] = []
    for lon, lat in polygon.exterior.coords:
        pair = [round(float(lon), 6), round(float(lat), 6)]
        if ring and ring[-1] == pair:
            continue
        ring.append(pair)
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(ring) < 3:
        return []
    return ring


def to_wkt(ring: list[list[float]]) -> str:
    closed = [*ring, ring[0]]
    body = ", ".join(f"{lon} {lat}" for lon, lat in closed)
    return f"POLYGON(({body}))"


def stored_polygon(session: AsyncSession, wkt: str) -> str | WKTElement:
    if session.get_bind().dialect.name == "sqlite":
        return wkt
    return WKTElement(wkt, srid=4326)


def read_ring(value: WKBElement | WKTElement | str) -> list[list[float]]:
    geometry = loads(value) if isinstance(value, str) else to_shape(value)
    if not isinstance(geometry, ShapePolygon):
        raise _invalid("Stored polygon is invalid")
    return normalize_ring([[float(lon), float(lat)] for lon, lat in geometry.exterior.coords])


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)
