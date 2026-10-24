import logging

from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)


def health_status() -> HealthResponse:
    logger.debug("health checked")
    return HealthResponse(status="ok")
