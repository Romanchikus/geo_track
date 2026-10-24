from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import allow_user_or_internal_token, get_current_user, get_db
from app.api.pagination import Page, get_page
from app.db.models.device import Device
from app.db.models.user import User
from app.schemas.devices import DeviceBatchCreate, DeviceCreate, DeviceResponse, DeviceUpdate
from app.services.devices.crud import create_device as create_device_service
from app.services.devices.crud import create_device_batch as create_device_batch_service
from app.services.devices.crud import delete_device as delete_device_service
from app.services.devices.crud import get_device as get_device_service
from app.services.devices.crud import list_all_devices as list_all_devices_service
from app.services.devices.crud import list_devices as list_devices_service
from app.services.devices.crud import update_device as update_device_service

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(
    body: DeviceCreate,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Device:
    return await create_device_service(db, body.name)


@router.post("/batch", response_model=list[DeviceResponse], status_code=status.HTTP_201_CREATED)
async def create_device_batch(
    body: DeviceBatchCreate,
    _: None = Depends(allow_user_or_internal_token),
    db: AsyncSession = Depends(get_db),
) -> list[Device]:
    return await create_device_batch_service(db, body.count)


@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    _: User = Depends(get_current_user),
    page: Page = Depends(get_page),
    db: AsyncSession = Depends(get_db),
) -> list[Device]:
    return await list_devices_service(db, page.limit, page.offset)


@router.get("/all", response_model=list[DeviceResponse])
async def list_all_devices(
    _: None = Depends(allow_user_or_internal_token),
    db: AsyncSession = Depends(get_db),
) -> list[Device]:
    return await list_all_devices_service(db)


@router.get("/{device_id}", response_model=DeviceResponse)
async def read_device(
    device_id: int,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Device:
    return await get_device_service(db, device_id)


@router.patch("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: int,
    body: DeviceUpdate,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Device:
    return await update_device_service(db, device_id, body.name)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: int,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_device_service(db, device_id)
