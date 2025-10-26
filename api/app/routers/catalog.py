from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import auth
from ..database import get_session
from ..models import Role
from ..schemas import RoleRead

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/roles", response_model=list[RoleRead])
async def list_roles(
    account_id: str | None = Query(default=None, alias="accountId"),
    q: str | None = None,
    tag: str | None = None,
    session: AsyncSession = Depends(get_session),
    user=Depends(auth.get_current_user),
) -> list[RoleRead]:
    stmt = select(Role).join(Role.account)
    if account_id:
        stmt = stmt.where(Role.account_id == account_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(Role.name.ilike(like))
    result = await session.execute(stmt)
    roles = result.scalars().unique().all()
    if tag:
        roles = [role for role in roles if role.tags.get(tag)]
    return [RoleRead.from_orm(role) for role in roles]
