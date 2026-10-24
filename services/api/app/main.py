import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api.middleware import RequestRateMiddleware
from app.api.routers import auth, devices, health, load, statistics, subscriptions, telemetry, users
from app.clients.redis import close_redis
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine
from app.services.telemetry.processing.sockets import websocket_manager
from app.services.traffic import start_request_counter, stop_request_counter
from app.workers.telemetry_partitions import register as register_partition_job

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("starting %s", settings.app_name)
    start_request_counter()
    scheduler = AsyncIOScheduler()
    register_partition_job(scheduler)
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await websocket_manager.stop()
        await stop_request_counter()
        await close_redis()
        await dispose_engine()
        logger.info("stopped %s", settings.app_name)


def create_app() -> FastAPI:
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
    app.add_middleware(RequestRateMiddleware)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(devices.router)
    app.include_router(telemetry.router)
    app.include_router(statistics.router)
    app.include_router(subscriptions.router)
    app.include_router(load.router)
    return app


app = create_app()
