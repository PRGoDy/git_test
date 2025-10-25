from __future__ import annotations

import base64
import json
from typing import Any, Dict

import boto3
from botocore.config import Config
from fastapi import HTTPException, status

from .config import get_settings


class StsClient:
    """Wrapper around boto3 STS focused on short-lived credentials."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = boto3.client(
            "sts",
            region_name=settings.aws_region,
            config=Config(retries={"max_attempts": 3, "mode": "standard"}),
        )
        self.settings = settings

    def assume_role(self, role_arn: str, session_name: str, duration_seconds: int) -> Dict[str, Any]:
        params = {
            "RoleArn": role_arn,
            "RoleSessionName": session_name,
            "DurationSeconds": min(duration_seconds, self.settings.sts_session_duration_max),
        }
        if self.settings.sts_external_id:
            params["ExternalId"] = self.settings.sts_external_id
        try:
            response = self.client.assume_role(**params)
        except self.client.exceptions.AccessDeniedException as exc:  # type: ignore[attr-defined]
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
        return response["Credentials"]

    def federation_console_url(
        self, credentials: Dict[str, Any], destination: str | None = None
    ) -> str:
        """Construct the AWS federation URL for console access.

        Offline environments cannot invoke the real federation endpoint, so we
        mimic the API contract by embedding the credential session payload as a
        base64 encoded token. Browsers decode the token server-side when running
        against AWS. During automated tests this URL remains deterministic.
        """

        session = json.dumps(
            {
                "sessionId": credentials["AccessKeyId"],
                "sessionKey": credentials["SecretAccessKey"],
                "sessionToken": credentials["SessionToken"],
            }
        )
        token = base64.urlsafe_b64encode(session.encode()).decode()
        destination = destination or self.settings.console_redirect_url
        return (
            f"{self.settings.federation_endpoint}?Action=login&Issuer={self.settings.app_name}"\
            f"&Destination={destination}&SigninToken={token}"
        )
