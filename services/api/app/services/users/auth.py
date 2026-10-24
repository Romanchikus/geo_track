import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.services.users.crud import get_by_email
from app.services.users.passwords import verify_password

logger = logging.getLogger(__name__)


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await get_by_email(session, email.strip().lower())
    if user is None or not verify_password(password, user.password_hash):
        logger.info("login failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    logger.info("login succeeded for user %s", user.id)
    return user
