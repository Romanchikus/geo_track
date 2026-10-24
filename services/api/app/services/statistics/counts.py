import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.device import Device
from app.db.models.subscription import Subscription
from app.db.models.telemetry import Telemetry
from app.db.models.user import User
from app.schemas.statistics import Statistics

logger = logging.getLogger(__name__)


async def count_statistics(session: AsyncSession) -> Statistics:
    """Count devices, users, subscriptions, and stored telemetry."""
    since = datetime.now(UTC) - timedelta(days=1)
    devices = select(func.count()).select_from(Device).scalar_subquery()
    telemetry = select(func.count()).select_from(Telemetry).scalar_subquery()
    telemetry_last_day = (
        select(func.count()).select_from(Telemetry).where(Telemetry.timestamp >= since).scalar_subquery()
    )
    subscriptions = select(func.count()).select_from(Subscription).scalar_subquery()
    users = select(func.count()).select_from(User).scalar_subquery()
    row = (
        await session.execute(
            select(
                devices.label("devices"),
                telemetry.label("telemetry"),
                telemetry_last_day.label("telemetry_last_day"),
                subscriptions.label("subscriptions"),
                users.label("users"),
            )
        )
    ).one()
    stats = Statistics(
        devices=row.devices,
        telemetry=row.telemetry,
        telemetry_last_day=row.telemetry_last_day,
        subscriptions=row.subscriptions,
        users=row.users,
    )
    logger.info(
        "statistics devices=%s telemetry=%s telemetry_last_day=%s subscriptions=%s users=%s",
        stats.devices,
        stats.telemetry,
        stats.telemetry_last_day,
        stats.subscriptions,
        stats.users,
    )
    return stats
