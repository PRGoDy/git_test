from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, BaseSettings, Field, validator


class Settings(BaseSettings):
    """Runtime configuration for the Access Hub API."""

    app_name: str = "Access Hub"
    api_prefix: str = "/api"
    database_url: str = Field(
        default="sqlite+aiosqlite:///./access_hub.db",
        description="SQLAlchemy database URL. Defaults to local SQLite for development.",
    )
    alembic_database_url: Optional[str] = Field(
        default=None, description="Override database URL used by Alembic migrations."
    )
    oidc_issuer: Optional[AnyHttpUrl] = Field(
        default=None, description="OIDC issuer URL used to validate ID tokens."
    )
    oidc_audience: Optional[str] = Field(
        default=None, description="OIDC audience/client ID expected in received ID tokens."
    )
    oidc_mfa_claim: str = Field(
        default="amr",
        description="Claim in the OIDC ID token that signals MFA has been satisfied.",
    )
    jwt_secret_key: str = Field(
        default="change-me",
        description="Secret key for signing application session JWTs.",
    )
    jwt_algorithm: str = "HS512"
    jwt_expiration_seconds: int = 3600
    cors_origins: List[str] = Field(default_factory=list)
    public_app_url: str = Field(
        default="http://localhost:3000",
        description="Public base URL for the frontend, used for device verification links.",
    )
    sts_external_id: Optional[str] = Field(
        default=None, description="External ID required when assuming AWS roles."
    )
    sts_session_duration_default: int = Field(
        default=3600, description="Default session duration for STS tokens."
    )
    sts_session_duration_max: int = Field(
        default=43200, description="Absolute maximum session duration allowed (12h)."
    )
    audit_retention_days: int = Field(
        default=365, description="Retention period for audit logs in days."
    )
    rate_limit_per_minute: int = Field(default=60)
    console_redirect_url: str = Field(
        default="https://console.aws.amazon.com/",
        description="AWS Console URL used for federated sign-in redirection.",
    )
    federation_endpoint: str = Field(
        default="https://signin.aws.amazon.com/federation",
        description="AWS federation endpoint to request sign-in tokens.",
    )
    aws_region: str = Field(default="us-east-1")
    worker_redis_url: str = Field(
        default="redis://redis:6379/0", description="Redis connection for the worker queue."
    )
    break_glass_keyword: str = Field(
        default="BREAKGLASS", description="Keyword required to bypass lint guardrails."
    )

    class Config:
        env_file = ".env"
        case_sensitive = False

    @validator("cors_origins", pre=True)
    def split_cors_origins(cls, value: str | List[str]) -> List[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache()
def get_settings() -> Settings:
    return Settings()
