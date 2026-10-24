import logging
import os
import shutil
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from geoalchemy2 import Geography, Geometry
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import settings
from app.db.base import Base
from app.db.session import dispose_engine, get_engine

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session", autouse=True)
def migrated() -> Iterator[None]:
    """Create a throwaway SQLite database and schema, then delete them."""
    token = uuid.uuid4().hex[:16]
    schema_name = f"pytest_{token}"
    root = Path(tempfile.mkdtemp(prefix=f"geo_pytest_{token}_"))
    database = root / "main.sqlite"
    previous_url = os.environ.get("DATABASE_URL")
    previous_schema = os.environ.get("DATABASE_SCHEMA")
    previous_settings_url = settings.database_url
    previous_settings_schema = settings.database_schema
    os.environ["DATABASE_URL"] = URL.create(drivername="sqlite+aiosqlite", database=str(database)).render_as_string(
        hide_password=False
    )
    os.environ["DATABASE_SCHEMA"] = schema_name
    settings.database_url = os.environ["DATABASE_URL"]
    settings.database_schema = schema_name
    spatial_indexes = _drop_spatial_indexes()
    _dispose()
    try:
        _create_tables(get_engine())
        logger.info("pytest sqlite database %s schema %s", database.name, schema_name)
        yield
    finally:
        _restore_spatial_indexes(spatial_indexes)
        _restore("DATABASE_URL", previous_url)
        _restore("DATABASE_SCHEMA", previous_schema)
        settings.database_url = previous_settings_url
        settings.database_schema = previous_settings_schema
        _dispose()
        shutil.rmtree(root, ignore_errors=True)


def _drop_spatial_indexes() -> list[tuple[Geography | Geometry, bool]]:
    """SQLite has no SpatiaLite here, so table creation must not ask for a spatial index."""
    changed: list[tuple[Geography | Geometry, bool]] = []
    for table in Base.metadata.tables.values():
        for column in table.columns:
            column_type = column.type
            if isinstance(column_type, (Geography, Geometry)) and column_type.spatial_index:
                changed.append((column_type, True))
                column_type.spatial_index = False
    return changed


def _restore_spatial_indexes(changed: list[tuple[Geography | Geometry, bool]]) -> None:
    for column_type, enabled in changed:
        column_type.spatial_index = enabled


def _create_tables(engine: AsyncEngine) -> None:
    import asyncio

    async def create() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create())


def _dispose() -> None:
    import asyncio

    asyncio.run(dispose_engine())


def _restore(name: str, previous: str | None) -> None:
    if previous is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = previous
