import logging
from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db import models as db_models  # noqa: F401

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def _create_engine() -> AsyncEngine:
    url = settings.database_url
    sqlite = url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if sqlite else {}
    if sqlite:
        engine = create_async_engine(url, connect_args=connect_args)
        _prepare_sqlite(engine)
    else:
        engine = create_async_engine(
            url,
            pool_pre_ping=True,
            connect_args=connect_args,
            pool_size=settings.pool_size,
            max_overflow=settings.pool_overflow,
        )
        logger.info(
            "database pool keeps %s idle connections and allows %s",
            settings.pool_size,
            settings.pool_size + settings.pool_overflow,
        )
    if settings.database_schema:
        engine = engine.execution_options(schema_translate_map={None: settings.database_schema})
    return engine


def _prepare_sqlite(engine: AsyncEngine) -> None:
    schema = settings.database_schema
    schema_path = ""
    if schema:
        database = make_url(settings.database_url).database
        schema_path = str(Path(database or "").with_name(f"{schema}.sqlite"))

    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        if schema:
            cursor.execute(f'ATTACH DATABASE "{schema_path}" AS {schema}')
        cursor.close()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
