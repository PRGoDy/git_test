from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import APIKeyCookie
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .database import get_session
from .models import DeviceSession, User

SESSION_COOKIE_NAME = "access_hub_session"


async def get_user_from_db(session: AsyncSession, sub: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.idp_sub == sub))
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, *, email: str, name: str, sub: str, mfa: bool) -> User:
    user = User(email=email, display_name=name, idp_sub=sub)
    if mfa:
        user.mfa_verified_at = datetime.utcnow()
    session.add(user)
    await session.flush()
    return user


async def update_user_mfa(user: User, mfa: bool) -> None:
    if mfa:
        user.mfa_verified_at = datetime.utcnow()


def _load_jwks(issuer: str) -> dict:
    jwks_url = issuer.rstrip("/") + "/.well-known/jwks.json"
    resp = httpx.get(jwks_url, timeout=5.0)
    resp.raise_for_status()
    return resp.json()


async def verify_oidc_token(id_token: str) -> dict:
    settings = get_settings()
    if not settings.oidc_issuer:
        # Development fallback: trust tokens signed with the application secret.
        try:
            claims = jwt.decode(
                id_token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                audience=settings.oidc_audience,
                options={"verify_aud": bool(settings.oidc_audience)},
            )
            return claims
        except JWTError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    jwks = _load_jwks(settings.oidc_issuer)
    unverified_header = jwt.get_unverified_header(id_token)
    kid = unverified_header.get("kid")
    key_data = next((k for k in jwks["keys"] if k["kid"] == kid), None)
    if not key_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown key")

    try:
        claims = jwt.decode(
            id_token,
            key_data,
            algorithms=[unverified_header["alg"]],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
        )
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return claims


async def issue_app_token(user: User) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.display_name,
        "mfa_verified_at": user.mfa_verified_at.isoformat() if user.mfa_verified_at else None,
        "exp": datetime.utcnow() + timedelta(seconds=settings.jwt_expiration_seconds),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.jwt_expiration_seconds,
    )


async def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    token: str | None = Depends(APIKeyCookie(name=SESSION_COOKIE_NAME, auto_error=False)),
) -> User:
    settings = get_settings()
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing session")
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def ensure_mfa(user: User) -> None:
    if not user.mfa_verified_at:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MFA required")


async def create_device_session(session: AsyncSession, verification_uri: str) -> DeviceSession:
    device_code = secrets.token_urlsafe(24)
    user_code = secrets.token_hex(3).upper()
    now = datetime.utcnow()
    device = DeviceSession(
        device_code=device_code,
        user_code=user_code,
        expires_at=now + timedelta(minutes=10),
        interval_seconds=5,
    )
    session.add(device)
    await session.flush()
    return device


async def activate_device_session(
    db_session: AsyncSession, user_code: str, user: User, token: str
) -> DeviceSession:
    result = await db_session.execute(
        select(DeviceSession).where(DeviceSession.user_code == user_code)
    )
    device = result.scalar_one_or_none()
    if not device or device.is_expired():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid user code")
    device.user_id = user.id
    device.mark_authorized(token)
    return device


async def poll_device_session(db_session: AsyncSession, device_code: str) -> DeviceSession:
    result = await db_session.execute(
        select(DeviceSession).where(DeviceSession.device_code == device_code)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid code")
    if device.is_expired():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Expired")
    return device
