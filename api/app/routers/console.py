from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .. import auth
from ..audit import record_audit
from ..aws import StsClient
from ..config import get_settings
from ..database import get_session
from ..schemas import ConsoleRequest, ConsoleResponse
from .sessions import _get_active_request

router = APIRouter(prefix="/console", tags=["console"])


@router.post("", response_model=ConsoleResponse)
async def open_console(
    payload: ConsoleRequest,
    current_user=Depends(auth.get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConsoleResponse:
    await auth.ensure_mfa(current_user)
    approved = await _get_active_request(session, current_user, payload.role_arn)
    if not approved:
        raise HTTPException(status_code=403, detail="No approved request")
    settings = get_settings()
    duration = min(payload.duration_seconds or settings.sts_session_duration_default, settings.sts_session_duration_max)
    sts = StsClient()
    creds = sts.assume_role(
        payload.role_arn,
        session_name=f"console-{current_user.id}",
        duration_seconds=duration,
    )
    url = sts.federation_console_url(creds, destination=payload.destination)
    await record_audit(
        session,
        user_id=current_user.id,
        action="console.launch",
        target=payload.role_arn,
        metadata={"destination": payload.destination},
    )
    return ConsoleResponse(redirect_url=url)
