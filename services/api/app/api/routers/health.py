from fastapi import APIRouter

from app.schemas.health import HealthResponse
from app.services.health import health_status

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    return health_status()
