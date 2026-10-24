import logging
import secrets
from collections.abc import AsyncIterator

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.user import User
from app.db.session import get_session_factory
from app.services.users.crud import find_user

logger = logging.getLogger(__name__)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a session. The use case commits. This rolls back on failure."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception as exc:
            await session.rollback()
            if not isinstance(exc, HTTPException):
                logger.exception("request failed; rolling back the database transaction")
            raise


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = await find_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


async def allow_user_or_internal_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_internal_token: str = Header(default=""),
) -> None:
    """Accept a signed-in user or the internal writer token."""
    expected = settings.internal_token
    if expected and x_internal_token and secrets.compare_digest(x_internal_token, expected):
        return
    await get_current_user(request, db)
