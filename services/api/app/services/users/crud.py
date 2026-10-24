import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.services.users.passwords import hash_password

logger = logging.getLogger(__name__)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def find_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def create_user(session: AsyncSession, email: str, password: str) -> User:
    user = User(email=_normalize_email(email), password_hash=hash_password(password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        logger.info("create user rejected; email already registered")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from None
    logger.info("created user %s", user.id)
    return user


async def get_user(session: AsyncSession, user_id: int) -> User:
    user = await find_user(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def list_users(session: AsyncSession, limit: int, offset: int) -> list[User]:
    stmt = select(User).order_by(User.id).limit(limit).offset(offset)
    result = await session.scalars(stmt)
    return list(result.all())


async def update_user(
    session: AsyncSession,
    current_user_id: int,
    user_id: int,
    email: str | None,
    password: str | None,
) -> User:
    if current_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    user = await get_user(session, user_id)
    if email is not None:
        user.email = _normalize_email(email)
    if password is not None:
        user.password_hash = hash_password(password)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        logger.info("update user rejected; email already registered")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from None
    logger.info("updated user %s", user.id)
    return user


async def delete_user(session: AsyncSession, current_user_id: int, user_id: int) -> None:
    if current_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    user = await get_user(session, user_id)
    await session.delete(user)
    await session.commit()
    logger.info("deleted user %s", user_id)
