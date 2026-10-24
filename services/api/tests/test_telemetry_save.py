from datetime import UTC, datetime

import pytest
from sqlalchemy.dialects import postgresql

from app.core.config import settings
from app.db import session as db_session
from app.schemas.telemetry import TelemetryPoint
from app.services.telemetry.processing.save import _merge_statement, _records


def test_merge_deduplicates_without_returning() -> None:
    statement = str(_merge_statement().compile(dialect=postgresql.dialect()))
    assert "INSERT INTO telemetry" in statement
    assert "pg_temp.telemetry_stage" in statement
    assert "ST_GeogFromText" in statement
    assert "DISTINCT ON" in statement
    assert "ON CONFLICT (device_id, timestamp) DO NOTHING" in statement
    assert "RETURNING" not in statement.upper()


def test_records_keep_arrival_order_as_wkt() -> None:
    stamp = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
    later = datetime(2026, 10, 23, 12, 1, tzinfo=UTC)
    records = _records(
        [
            TelemetryPoint(device_id=7, latitude=55.75, longitude=37.61, timestamp=stamp),
            TelemetryPoint(device_id=7, latitude=1, longitude=2, timestamp=stamp),
            TelemetryPoint(device_id=8, latitude=10, longitude=20, timestamp=later),
        ]
    )
    assert records == [
        (0, 7, "POINT(37.61 55.75)", stamp),
        (1, 7, "POINT(2.0 1.0)", stamp),
        (2, 8, "POINT(20.0 10.0)", later),
    ]


def test_engine_uses_the_configured_pool_size(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def create(url: str, **kwargs: object) -> object:
        del url
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(db_session, "create_async_engine", create)
    monkeypatch.setattr(settings, "database_schema", "")
    monkeypatch.setattr(settings, "database_url", "postgresql+asyncpg://geo:geo@localhost/geo_track")
    monkeypatch.setattr(settings, "pool_size", 4)
    monkeypatch.setattr(settings, "pool_overflow", 6)
    db_session._engine = None
    db_session._session_factory = None
    try:
        db_session.get_engine()
        db_session.get_engine()
    finally:
        db_session._engine = None
        db_session._session_factory = None

    assert calls == [{"pool_pre_ping": True, "connect_args": {}, "pool_size": 4, "max_overflow": 6}]
