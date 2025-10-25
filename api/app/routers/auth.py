from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import auth
from ..audit import record_audit
from ..config import get_settings
from ..database import get_session
from ..models import User
from ..schemas import (
    DeviceActivateRequest,
    DevicePollRequest,
    DevicePollResponse,
    DeviceStartResponse,
    UserRead,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/oidc/callback", response_model=UserRead)
async def oidc_callback(payload: dict, response: Response, session: AsyncSession = Depends(get_session)) -> UserRead:
    id_token = payload.get("id_token")
    if not id_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="id_token missing")
    claims = await auth.verify_oidc_token(id_token)
    email = claims.get("email")
    sub = claims.get("sub")
    name = claims.get("name") or email
    if not email or not sub:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid claims")

    mfa_claim = claims.get(get_settings().oidc_mfa_claim)
    mfa = False
    if isinstance(mfa_claim, list):
        mfa = "mfa" in [c.lower() for c in mfa_claim]
    elif isinstance(mfa_claim, str):
        mfa = mfa_claim.lower() == "mfa"

    result = await session.execute(select(User).where(User.idp_sub == sub))
    user = result.scalar_one_or_none()
    if not user:
        user = await auth.create_user(session, email=email, name=name, sub=sub, mfa=mfa)
        await record_audit(session, user_id=user.id, action="user.created", target=user.email)
    else:
        await auth.update_user_mfa(user, mfa)

    token = await auth.issue_app_token(user)
    await auth.set_session_cookie(response, token)
    await record_audit(session, user_id=user.id, action="auth.login", target=user.email)
    return UserRead.from_orm(user)


@router.post("/logout")
async def logout(response: Response) -> dict:
    await auth.clear_session_cookie(response)
    return {"ok": True}


@router.post("/device/start", response_model=DeviceStartResponse)
async def start_device_flow(
    request: Request, session: AsyncSession = Depends(get_session)
) -> DeviceStartResponse:
    settings = get_settings()
    verification_uri = f"{settings.public_app_url.rstrip('/')}/device"
    device = await auth.create_device_session(session, verification_uri)
    return DeviceStartResponse(
        device_code=device.device_code,
        user_code=device.user_code,
        verification_uri=f"{verification_uri}?user_code={device.user_code}",
        expires_in=600,
        interval=device.interval_seconds,
    )


@router.post("/device/activate")
async def activate_device(
    payload: DeviceActivateRequest,
    current_user: User = Depends(auth.get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    token = await auth.issue_app_token(current_user)
    await auth.activate_device_session(session, payload.user_code, current_user, token)
    await record_audit(
        session,
        user_id=current_user.id,
        action="auth.device.approved",
        metadata={"user_code": payload.user_code},
    )
    return {"ok": True}


@router.post("/device/poll", response_model=DevicePollResponse)
async def poll_device(payload: DevicePollRequest, session: AsyncSession = Depends(get_session)) -> DevicePollResponse:
    device = await auth.poll_device_session(session, payload.device_code)
    if device.can_poll():
        return DevicePollResponse(access_token=device.token, expires_in=300, status="authorized")
    return DevicePollResponse(access_token=None, expires_in=None, status="pending")
