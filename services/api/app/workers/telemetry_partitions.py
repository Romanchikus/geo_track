import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.db.session import get_session_factory
from app.services.telemetry.partitions import create_upcoming_partitions

logger = logging.getLogger(__name__)


def register(scheduler: AsyncIOScheduler) -> None:
    """Keep hourly PostgreSQL partitions ahead of incoming telemetry. Requests never do this."""
    interval = max(settings.telemetry_partition_interval_seconds, 1)
    scheduler.add_job(
        run_partition_maintenance,
        IntervalTrigger(seconds=interval),
        id="telemetry-partitions",
        next_run_time=datetime.now(UTC),
        max_instances=1,
        coalesce=True,
    )
    logger.info("scheduled telemetry-partitions every %ss", interval)


async def run_partition_maintenance() -> None:
    if settings.database_url.startswith("sqlite"):
        logger.info("skipping telemetry partition maintenance on sqlite")
        return
    factory = get_session_factory()
    async with factory() as session:
        try:
            await create_upcoming_partitions(session)
        except Exception:
            await session.rollback()
            raise
