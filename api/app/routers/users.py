from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import auth
from ..schemas import UserRead

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_me(current_user=Depends(auth.get_current_user)) -> UserRead:
    return UserRead.from_orm(current_user)
