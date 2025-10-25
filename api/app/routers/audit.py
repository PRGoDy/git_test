from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import auth
from ..database import get_session
from ..models import AuditLog
from ..schemas import AuditLogRead

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogRead])
async def list_audit_logs(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(auth.get_current_user),
) -> list[AuditLogRead]:
    result = await session.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200))
    logs = result.scalars().all()
    return [AuditLogRead.from_orm(log) for log in logs]
