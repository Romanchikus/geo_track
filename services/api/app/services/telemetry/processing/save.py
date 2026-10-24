import logging
import time
from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, MetaData, Table, Text, func, select, text
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.dml import Insert

from app.db.models.telemetry import Telemetry
from app.db.session import get_engine, get_session_factory
from app.schemas.telemetry import TelemetryPoint

logger = logging.getLogger(__name__)

# SQLite rejects statements with too many bound parameters (3 columns per row).
_SQLITE_PAGE = 5_000
# COPY has no parameter limit. Each page is one connection, one commit.
_POSTGRES_PAGE = 50_000

_STAGE = Table(
    "telemetry_stage",
    MetaData(),
    Column("ordinal", Integer, nullable=False),
    Column("device_id", BigInteger, nullable=False),
    Column("location", Text, nullable=False),
    Column("timestamp", DateTime(timezone=True), nullable=False),
    schema="pg_temp",
)

_CREATE_STAGE = text(
    """
    CREATE TEMP TABLE telemetry_stage (
        ordinal INTEGER NOT NULL,
        device_id BIGINT NOT NULL,
        location TEXT NOT NULL,
        "timestamp" TIMESTAMPTZ NOT NULL
    ) ON COMMIT DROP
    """
)

TelemetryRecord = tuple[int, int, str, datetime]


async def save_telemetry_batch(points: list[TelemetryPoint], is_sqlite: bool) -> int:
    """Insert points and return how many new rows were stored."""
    if not points:
        return 0
    started = time.perf_counter()
    if is_sqlite:
        inserted = await _insert_sqlite(points)
    else:
        inserted = await _insert_postgres(points)
    logger.info(
        "inserted %s telemetry rows from %s points in %.3fs",
        inserted,
        len(points),
        time.perf_counter() - started,
    )
    return inserted


async def _insert_sqlite(points: list[TelemetryPoint]) -> int:
    inserted = 0
    for page in _pages(points, _SQLITE_PAGE):
        inserted += await _insert_sqlite_page(page)
    return inserted


async def _insert_sqlite_page(points: list[TelemetryPoint]) -> int:
    rows = [_sqlite_row(point) for point in points]
    factory = _worker_factory()
    started = time.perf_counter()
    try:
        async with factory() as session, session.begin():
            result = await session.execute(_sqlite_statement(rows))
            inserted = _inserted_count(result)
    except Exception:
        logger.exception("failed to insert sqlite telemetry page of %s", len(points))
        raise
    logger.info(
        "inserted sqlite telemetry page of %s in %.3fs, stored %s",
        len(points),
        time.perf_counter() - started,
        inserted,
    )
    return inserted


async def _insert_postgres(points: list[TelemetryPoint]) -> int:
    inserted = 0
    factory = get_session_factory()
    for page in _pages(points, _POSTGRES_PAGE):
        inserted += await _insert_postgres_page(page, factory)
    return inserted


async def _insert_postgres_page(points: list[TelemetryPoint], factory: async_sessionmaker[AsyncSession]) -> int:
    records = _records(points)
    started = time.perf_counter()
    try:
        async with factory() as session, session.begin():
            await session.execute(_CREATE_STAGE)
            copied = time.perf_counter()
            await _copy_stage(session, records)
            copy_seconds = time.perf_counter() - copied
            merged = time.perf_counter()
            result = await session.execute(_merge_statement())
            inserted = _inserted_count(result)
            merge_seconds = time.perf_counter() - merged
    except Exception:
        logger.exception("failed to merge telemetry page of %s", len(points))
        raise
    logger.info(
        "copied %s telemetry rows into staging in %.3fs and merged %s in %.3fs (page %.3fs)",
        len(records),
        copy_seconds,
        inserted,
        merge_seconds,
        time.perf_counter() - started,
    )
    return inserted


def _worker_factory() -> async_sessionmaker[AsyncSession]:
    """One session factory per SQLite page."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


def _records(points: list[TelemetryPoint]) -> list[TelemetryRecord]:
    return [(ordinal, point.device_id, _wkt(point), point.timestamp) for ordinal, point in enumerate(points)]


def _sqlite_row(point: TelemetryPoint) -> dict[str, object]:
    return {
        "device_id": point.device_id,
        "location": _wkt(point),
        "timestamp": point.timestamp,
    }


def _wkt(point: TelemetryPoint) -> str:
    return f"POINT({point.longitude} {point.latitude})"


def _sqlite_statement(rows: list[dict[str, object]]) -> Insert:
    return sqlite_insert(Telemetry).values(rows).on_conflict_do_nothing(index_elements=["device_id", "timestamp"])


def _merge_statement() -> Insert:
    """Copy leaves WKT as text. PostgreSQL converts it while discarding duplicate keys."""
    chosen = (
        select(
            _STAGE.c.device_id,
            func.ST_GeogFromText(_STAGE.c.location).label("location"),
            _STAGE.c.timestamp,
        )
        .ext(distinct_on(_STAGE.c.device_id, _STAGE.c.timestamp))
        .order_by(_STAGE.c.device_id, _STAGE.c.timestamp, _STAGE.c.ordinal)
    )
    return (
        postgres_insert(Telemetry)
        .from_select(["device_id", "location", "timestamp"], chosen, include_defaults=False)
        .on_conflict_do_nothing(index_elements=["device_id", "timestamp"])
    )


async def _copy_stage(session: AsyncSession, records: list[TelemetryRecord]) -> None:
    connection = await session.connection()
    raw = await connection.get_raw_connection()
    driver = raw.driver_connection
    if driver is None:
        raise RuntimeError("telemetry copy requires asyncpg")
    asyncpg_connection = getattr(driver, "_connection", driver)
    copy = getattr(asyncpg_connection, "copy_records_to_table", None)
    if copy is None:
        raise RuntimeError("telemetry copy requires asyncpg")
    await copy(
        "telemetry_stage",
        records=records,
        columns=["ordinal", "device_id", "location", "timestamp"],
        schema_name="pg_temp",
    )


def _inserted_count(result: object) -> int:
    if not isinstance(result, CursorResult) or result.rowcount < 0:
        raise RuntimeError("telemetry insert did not report a row count")
    return result.rowcount


def _pages(points: list[TelemetryPoint], size: int) -> Iterator[list[TelemetryPoint]]:
    for start in range(0, len(points), size):
        yield points[start : start + size]
