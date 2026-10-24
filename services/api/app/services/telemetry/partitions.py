import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

CREATE_UPCOMING_PARTITIONS = """
DO $$
DECLARE
    hour_start TIMESTAMPTZ;
    partition_name TEXT;
BEGIN
    PERFORM pg_advisory_xact_lock(74021021);
    FOR i IN 0..23 LOOP
        hour_start := date_trunc('hour', NOW() AT TIME ZONE 'UTC')
                      AT TIME ZONE 'UTC'
                      + i * INTERVAL '1 hour';

        partition_name := 'telemetry_' ||
                          to_char(hour_start AT TIME ZONE 'UTC', 'YYYYMMDD_HH24');

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF telemetry
             FOR VALUES FROM (%L) TO (%L)',
            partition_name,
            hour_start,
            hour_start + INTERVAL '1 hour'
        );
    END LOOP;
END $$;
"""


async def create_upcoming_partitions(session: AsyncSession) -> None:
    """Create the next 24 hourly telemetry partitions. Only the maintenance job calls this."""
    await session.execute(text(CREATE_UPCOMING_PARTITIONS))
    await session.commit()
    logger.info("ensured telemetry partitions for the next 24 hours")
