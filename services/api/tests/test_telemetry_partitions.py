from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.workers.telemetry_partitions import register


def test_partition_job_is_scheduled_hourly() -> None:
    scheduler = AsyncIOScheduler()
    register(scheduler)
    job = scheduler.get_job("telemetry-partitions")
    assert job is not None
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval.total_seconds() == 3600
