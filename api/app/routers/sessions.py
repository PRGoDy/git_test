from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import auth
from ..audit import record_audit
from ..aws import StsClient
from ..config import get_settings
from ..database import get_session
from ..models import AccessRequest, SessionEvent, User
from ..schemas import SessionCredentials, SessionRequest

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _get_active_request(session: AsyncSession, user: User, role_arn: str) -> AccessRequest | None:
    stmt = select(AccessRequest).where(
        AccessRequest.requester_id == user.id,
        AccessRequest.status == "approved",
    )
    result = await session.execute(stmt)
    for req in result.scalars().all():
        if role_arn in req.role_arns:
            return req
    return None


@router.post("", response_model=SessionCredentials)
async def create_session(
    payload: SessionRequest,
    request: Request,
    current_user: User = Depends(auth.get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SessionCredentials:
    await auth.ensure_mfa(current_user)
    settings = get_settings()
    duration = payload.duration_seconds or settings.sts_session_duration_default
    duration = min(duration, settings.sts_session_duration_max)

    approved = await _get_active_request(session, current_user, payload.role_arn)
    if not approved:
        raise HTTPException(status_code=403, detail="No approved request")

    sts = StsClient()
    creds = sts.assume_role(
        payload.role_arn,
        session_name=f"accesshub-{current_user.id}",
        duration_seconds=duration,
    )
    event = SessionEvent(
        user_id=current_user.id,
        role_arn=payload.role_arn,
        duration_seconds=duration,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "unknown"),
    )
    session.add(event)
    await session.flush()
    await record_audit(
        session,
        user_id=current_user.id,
        action="session.issued",
        target=payload.role_arn,
        metadata={"duration": duration, "session_event_id": str(event.id)},
    )
    return SessionCredentials(**creds, region=settings.aws_region)
