from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid4, primary_key=True, index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    idp_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    mfa_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    requests: Mapped[List["AccessRequest"]] = relationship(back_populates="requester")


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    env: Mapped[str] = mapped_column(String(64), nullable=False)
    owners: Mapped[List[str]] = mapped_column(JSON, default=list)

    roles: Mapped[List["Role"]] = relationship(back_populates="account")


class Role(Base):
    __tablename__ = "roles"

    arn: Mapped[str] = mapped_column(String(2048), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(12), ForeignKey("accounts.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sensitivity_tag: Mapped[str] = mapped_column(String(64), default="low")
    default_duration_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    tags: Mapped[dict] = mapped_column(JSON, default=dict)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)

    account: Mapped[Account] = relationship(back_populates="roles")


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True, index=True)
    requester_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    role_arns: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    approver_ids: Mapped[List[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    break_glass: Mapped[bool] = mapped_column(Boolean, default=False)

    requester: Mapped[User] = relationship(back_populates="requests")


class SessionEvent(Base):
    __tablename__ = "session_events"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    role_arn: Mapped[str] = mapped_column(String(2048), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(64))
    user_agent: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    target: Mapped[Optional[str]] = mapped_column(String(512))
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class PolicyTemplate(Base):
    __tablename__ = "policy_templates"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    json: Mapped[dict] = mapped_column(JSON, nullable=False)
    owner_team: Mapped[str] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class DeviceSession(Base):
    __tablename__ = "device_sessions"

    device_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=5)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    authorized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    token: Mapped[Optional[str]] = mapped_column(String(4096))

    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at

    def mark_authorized(self, token: str) -> None:
        self.authorized_at = datetime.utcnow()
        self.token = token

    def can_poll(self) -> bool:
        return not self.is_expired() and self.token is not None
