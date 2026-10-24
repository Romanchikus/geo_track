from fastapi import APIRouter, Depends, HTTPException, status
from redis.exceptions import RedisError

from app.api.dependencies import allow_user_or_internal_token
from app.schemas.load import LoadControl, LoadUpdate
from app.services.load import read_load, update_load

router = APIRouter(prefix="/load", tags=["load"])


@router.get("", response_model=LoadControl)
async def get_load(_: None = Depends(allow_user_or_internal_token)) -> LoadControl:
    try:
        return await read_load()
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Load control is unavailable",
        ) from exc


@router.patch("", response_model=LoadControl)
async def patch_load(body: LoadUpdate, _: None = Depends(allow_user_or_internal_token)) -> LoadControl:
    try:
        return await update_load(body)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Load control is unavailable",
        ) from exc
