from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.api.pagination import Page, get_page
from app.db.models.user import User
from app.schemas.users import UserCreate, UserResponse, UserUpdate
from app.services.users.crud import create_user as create_user_service
from app.services.users.crud import delete_user as delete_user_service
from app.services.users.crud import get_user as get_user_service
from app.services.users.crud import list_users as list_users_service
from app.services.users.crud import update_user as update_user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    return await create_user_service(db, body.email, body.password)


@router.get("", response_model=list[UserResponse])
async def list_users(
    _: User = Depends(get_current_user),
    page: Page = Depends(get_page),
    db: AsyncSession = Depends(get_db),
) -> list[User]:
    return await list_users_service(db, page.limit, page.offset)


@router.get("/me", response_model=UserResponse)
async def read_me(current: User = Depends(get_current_user)) -> User:
    return current


@router.get("/{user_id}", response_model=UserResponse)
async def read_user(
    user_id: int,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await get_user_service(db, user_id)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await update_user_service(db, current.id, user_id, body.email, body.password)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    request: Request,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_user_service(db, current.id, user_id)
    request.session.clear()
