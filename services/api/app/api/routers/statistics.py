from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.schemas.statistics import Statistics
from app.services.statistics.counts import count_statistics

router = APIRouter(prefix="/statistics", tags=["statistics"])


@router.get("", response_model=Statistics)
async def read_statistics(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Statistics:
    return await count_statistics(db)
