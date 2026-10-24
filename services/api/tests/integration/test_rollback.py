import pytest
from sqlalchemy import text

from app.db.session import dispose_engine, get_session_factory

pytestmark = pytest.mark.integration


async def test_uncommitted_insert_rolls_back() -> None:
    factory = get_session_factory()
    try:
        async with factory() as session:
            await session.execute(text("CREATE TABLE IF NOT EXISTS rollback_probe (id integer PRIMARY KEY)"))
            await session.execute(text("DELETE FROM rollback_probe"))
            await session.commit()

        async with factory() as session:
            await session.execute(text("INSERT INTO rollback_probe (id) VALUES (1)"))
            await session.rollback()

        async with factory() as session:
            count = await session.scalar(text("SELECT count(id) FROM rollback_probe"))
            assert count == 0
    finally:
        try:
            async with factory() as session:
                await session.execute(text("DROP TABLE IF EXISTS rollback_probe"))
                await session.commit()
        finally:
            await dispose_engine()
