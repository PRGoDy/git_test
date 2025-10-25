from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

import requests
import typer

DEFAULT_API_URL = os.environ.get("ACCESS_HUB_API", "http://localhost:8000/api")
TOKEN_PATH = Path.home() / ".access-hub" / "token.json"

app = typer.Typer(help="CLI for interacting with Access Hub")


def _ensure_storage() -> Path:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    return TOKEN_PATH


def _save_token(token: str) -> None:
    path = _ensure_storage()
    path.write_text(json.dumps({"token": token, "saved_at": time.time()}))


def _load_token() -> Optional[str]:
    if not TOKEN_PATH.exists():
        return None
    data = json.loads(TOKEN_PATH.read_text())
    return data.get("token")


def _auth_headers() -> dict[str, str]:
    token = _load_token()
    if not token:
        typer.echo("Not logged in. Run `hub login` first.")
        raise typer.Exit(1)
    return {"Authorization": f"Bearer {token}"}


@app.command()
def login(api: str = DEFAULT_API_URL) -> None:
    """Authenticate using the device code flow."""

    response = requests.post(f"{api}/auth/device/start")
    response.raise_for_status()
    payload = response.json()
    typer.echo("Visit the URL below and enter the user code:")
    typer.echo(f"  {payload['verification_uri']}")
    typer.echo(f"User code: {payload['user_code']}")
    device_code = payload["device_code"]
    interval = payload.get("interval", 5)

    typer.echo("Waiting for approval...")
    while True:
        poll = requests.post(f"{api}/auth/device/poll", json={"device_code": device_code})
        poll.raise_for_status()
        data = poll.json()
        if data["status"] == "authorized" and data.get("access_token"):
            _save_token(data["access_token"])
            typer.echo("Login successful.")
            return
        time.sleep(interval)


@app.command()
def roles(api: str = DEFAULT_API_URL) -> None:
    """List catalog roles available to the user."""

    headers = _auth_headers()
    response = requests.get(f"{api}/catalog/roles", headers=headers)
    if response.status_code == 401:
        typer.echo("Unauthorized. Re-run login.")
        raise typer.Exit(1)
    response.raise_for_status()
    roles = response.json()
    for role in roles:
        account = role.get("account", {})
        account_name = account.get("name", "unknown")
        typer.echo(f"{role['arn']}\t{role['name']} ({account_name})")


def _format_export(creds: dict[str, str]) -> str:
    lines = [
        f"export AWS_ACCESS_KEY_ID={creds['AccessKeyId']}",
        f"export AWS_SECRET_ACCESS_KEY={creds['SecretAccessKey']}",
        f"export AWS_SESSION_TOKEN={creds['SessionToken']}",
    ]
    return "\n".join(lines)


@app.command()
def export(role_arn: str, duration: int = typer.Option(3600), api: str = DEFAULT_API_URL) -> None:
    """Request credentials and print shell exports."""

    headers = _auth_headers()
    response = requests.post(
        f"{api}/sessions",
        headers=headers,
        json={"role_arn": role_arn, "duration_seconds": duration, "output_mode": "export"},
    )
    if response.status_code == 403:
        typer.echo("Access denied. Ensure request approval and MFA.")
        raise typer.Exit(1)
    response.raise_for_status()
    creds = response.json()
    typer.echo(_format_export(creds))


@app.command("credential-process")
def credential_process(role_arn: str, duration: int = typer.Option(3600), api: str = DEFAULT_API_URL) -> None:
    """Emit JSON payload compatible with AWS credential_process."""

    headers = _auth_headers()
    response = requests.post(
        f"{api}/sessions",
        headers=headers,
        json={"role_arn": role_arn, "duration_seconds": duration, "output_mode": "credential_process"},
    )
    response.raise_for_status()
    creds = response.json()
    output = {
        "Version": 1,
        "AccessKeyId": creds["AccessKeyId"],
        "SecretAccessKey": creds["SecretAccessKey"],
        "SessionToken": creds["SessionToken"],
        "Expiration": creds["Expiration"],
    }
    typer.echo(json.dumps(output))


if __name__ == "__main__":
    app()
