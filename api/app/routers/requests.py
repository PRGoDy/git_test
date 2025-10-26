from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import auth
from ..audit import record_audit
from ..config import get_settings
from ..database import get_session
from ..models import AccessRequest, Role, User
from ..policy import lint_policy
from ..schemas import AccessRequestCreate, AccessRequestDecision, AccessRequestRead, PolicyLintRequest, PolicyLintResponse

router = APIRouter(prefix="/requests", tags=["requests"])


async def _ensure_roles(session: AsyncSession, role_arns: list[str]) -> list[Role]:
    stmt = select(Role).where(Role.arn.in_(role_arns))
    result = await session.execute(stmt)
    roles = result.scalars().all()
    if len(roles) != len(role_arns):
        missing = set(role_arns) - {role.arn for role in roles}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Roles not found: {missing}")
    return roles


@router.post("", response_model=AccessRequestRead, status_code=status.HTTP_201_CREATED)
async def create_request(
    payload: AccessRequestCreate,
    current_user: User = Depends(auth.get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AccessRequestRead:
    roles = await _ensure_roles(session, payload.role_arns)
    settings = get_settings()
    duration = min(payload.duration_seconds, settings.sts_session_duration_max)
    duration = max(duration, 900)
    break_glass = payload.break_glass

    if break_glass and settings.break_glass_keyword not in payload.justification.upper():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Break glass keyword missing")

    req = AccessRequest(
        requester_id=current_user.id,
        role_arns=payload.role_arns,
        justification=payload.justification,
        duration_seconds=duration,
        status="pending",
        break_glass=break_glass,
    )
    session.add(req)
    await session.flush()

    await record_audit(
        session,
        user_id=current_user.id,
        action="request.created",
        target=str(req.id),
        metadata={"role_arns": payload.role_arns, "duration": duration},
    )
    return AccessRequestRead.from_orm(req)


@router.get("/{request_id}", response_model=AccessRequestRead)
async def get_request(
    request_id: uuid.UUID,
    current_user: User = Depends(auth.get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AccessRequestRead:
    result = await session.execute(select(AccessRequest).where(AccessRequest.id == request_id))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if req.requester_id != current_user.id and str(current_user.id) not in req.approver_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return AccessRequestRead.from_orm(req)


@router.post("/{request_id}/approve", response_model=AccessRequestRead)
async def approve_request(
    request_id: uuid.UUID,
    payload: AccessRequestDecision,
    current_user: User = Depends(auth.get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AccessRequestRead:
    result = await session.execute(select(AccessRequest).where(AccessRequest.id == request_id))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already decided")
    req.status = "approved" if payload.approve else "denied"
    req.decided_at = datetime.utcnow()
    approver_id = payload.approver_id or str(current_user.id)
    req.approver_ids.append(approver_id)
    await record_audit(
        session,
        user_id=current_user.id,
        action="request.decided",
        target=str(req.id),
        metadata={"approved": payload.approve},
    )
    return AccessRequestRead.from_orm(req)


@router.post("/{request_id}/deny", response_model=AccessRequestRead)
async def deny_request(
    request_id: uuid.UUID,
    current_user: User = Depends(auth.get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AccessRequestRead:
    return await approve_request(
        request_id,
        AccessRequestDecision(approve=False, approver_id=str(current_user.id)),
        current_user,
        session,
    )


@router.post("/lint", response_model=PolicyLintResponse)
async def lint_endpoint(payload: PolicyLintRequest, current_user: User = Depends(auth.get_current_user)) -> PolicyLintResponse:
    return lint_policy(payload.policy_json, justification=payload.justification)
