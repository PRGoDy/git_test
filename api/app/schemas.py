from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class UserRead(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    mfa_verified_at: Optional[datetime]

    class Config:
        orm_mode = True


class AccountRead(BaseModel):
    id: str
    name: str
    env: str
    owners: List[str] = []

    class Config:
        orm_mode = True


class RoleRead(BaseModel):
    arn: str
    account_id: str
    name: str
    sensitivity_tag: str
    default_duration_seconds: int
    tags: dict
    requires_approval: bool
    account: Optional[AccountRead]

    class Config:
        orm_mode = True


class AccessRequestCreate(BaseModel):
    role_arns: List[str] = Field(..., min_items=1)
    justification: str = Field(..., min_length=10)
    duration_seconds: int = Field(..., ge=900)
    break_glass: bool = False


class AccessRequestRead(BaseModel):
    id: uuid.UUID
    requester_id: uuid.UUID
    role_arns: List[str]
    justification: str
    duration_seconds: int
    status: str
    approver_ids: List[str]
    created_at: datetime
    decided_at: Optional[datetime]
    break_glass: bool

    class Config:
        orm_mode = True


class AccessRequestDecision(BaseModel):
    approve: bool
    approver_id: Optional[str] = None
    justification: Optional[str] = None


class SessionRequest(BaseModel):
    role_arn: str
    duration_seconds: Optional[int]
    output_mode: str = Field(default="json", regex="^(json|export|credential_process)$")


class SessionCredentials(BaseModel):
    access_key_id: str = Field(alias="AccessKeyId")
    secret_access_key: str = Field(alias="SecretAccessKey")
    session_token: str = Field(alias="SessionToken")
    expiration: datetime = Field(alias="Expiration")
    region: str

    class Config:
        allow_population_by_field_name = True


class ConsoleRequest(BaseModel):
    role_arn: str
    duration_seconds: Optional[int]
    destination: Optional[str] = None


class ConsoleResponse(BaseModel):
    redirect_url: str


class PolicyLintRequest(BaseModel):
    policy_json: dict
    justification: Optional[str]


class PolicyFinding(BaseModel):
    severity: str
    message: str
    path: str


class PolicyLintResponse(BaseModel):
    valid: bool
    findings: List[PolicyFinding]


class DeviceStartResponse(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


class DevicePollRequest(BaseModel):
    device_code: str


class DevicePollResponse(BaseModel):
    access_token: Optional[str]
    expires_in: Optional[int]
    status: str


class DeviceActivateRequest(BaseModel):
    user_code: str


class AuditLogRead(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    action: str
    target: Optional[str]
    metadata: dict
    created_at: datetime

    class Config:
        orm_mode = True
