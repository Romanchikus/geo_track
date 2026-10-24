from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, WebSocket, status
from fastapi.responses import Response
from fastapi_filters import SortingValues, create_sorting
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.api.pagination import Page, get_page
from app.db.models.user import User
from app.schemas.telemetry import TelemetryFilters
from app.services.telemetry.batches import BatchMissingError, batch_body
from app.services.telemetry.crud import get_telemetry as get_telemetry_service
from app.services.telemetry.crud import list_telemetry as list_telemetry_service
from app.services.telemetry.processing.sockets import websocket_manager

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.websocket("/live")
async def telemetry_live(websocket: WebSocket) -> None:
    await websocket_manager.serve(websocket)


@router.get("/batches/{batch_id}")
async def read_telemetry_batch(
    batch_id: Annotated[int, Path(ge=1)],
    _: User = Depends(get_current_user),
) -> Response:
    try:
        body = await batch_body(batch_id)
    except BatchMissingError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found") from None
    return Response(content=body, media_type="application/octet-stream")


@router.get("")
async def list_telemetry(
    db: AsyncSession = Depends(get_db),
    filters: TelemetryFilters = Depends(),
    sorting: SortingValues = Depends(create_sorting("device_id", "timestamp", default="+timestamp")),
    page: Page = Depends(get_page),
    _: User = Depends(get_current_user),
) -> list[dict[str, object]]:
    return await list_telemetry_service(db, filters, sorting, page.limit, page.offset)


@router.get("/{device_id}/{timestamp}")
async def read_telemetry(
    device_id: int,
    timestamp: datetime,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await get_telemetry_service(db, device_id, timestamp)
