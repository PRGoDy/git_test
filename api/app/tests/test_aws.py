from __future__ import annotations

from app.aws import StsClient


def test_console_url_contains_token(monkeypatch):
    client = StsClient()

    creds = {
        "AccessKeyId": "ASIA123",
        "SecretAccessKey": "secret",
        "SessionToken": "token",
    }
    url = client.federation_console_url(creds, destination="https://console.aws.amazon.com/")
    assert "SigninToken" in url
    assert "https://console.aws.amazon.com/" in url
