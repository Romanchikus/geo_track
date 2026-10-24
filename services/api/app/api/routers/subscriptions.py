from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.api.pagination import Page, get_page
from app.db.models.user import User
from app.schemas.subscriptions import SubscriptionArea, SubscriptionCreate, SubscriptionUpdate
from app.services.subscriptions.crud import create_subscription as create_subscription_service
from app.services.subscriptions.crud import delete_subscription as delete_subscription_service
from app.services.subscriptions.crud import get_subscription as get_subscription_service
from app.services.subscriptions.crud import list_subscriptions as list_subscriptions_service
from app.services.subscriptions.crud import update_subscription as update_subscription_service

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.post("", response_model=SubscriptionArea, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    body: SubscriptionCreate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionArea:
    return await create_subscription_service(db, current.id, body)


@router.get("", response_model=list[SubscriptionArea])
async def list_subscriptions(
    current: User = Depends(get_current_user),
    page: Page = Depends(get_page),
    db: AsyncSession = Depends(get_db),
) -> list[SubscriptionArea]:
    return await list_subscriptions_service(db, current.id, page.limit, page.offset)


@router.get("/{polygon_id}", response_model=SubscriptionArea)
async def read_subscription(
    polygon_id: int,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionArea:
    return await get_subscription_service(db, current.id, polygon_id)


@router.patch("/{polygon_id}", response_model=SubscriptionArea)
async def update_subscription(
    polygon_id: int,
    body: SubscriptionUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionArea:
    return await update_subscription_service(db, current.id, polygon_id, body)


@router.delete("/{polygon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    polygon_id: int,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_subscription_service(db, current.id, polygon_id)
