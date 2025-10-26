from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import requests
import typer

DEFAULT_API_URL = os.environ.get("ACCESS_HUB_API", "http://localhost:8000/api")
RUNTIME_DIR = Path.home() / ".access-hub"
SOCKET_PATH = RUNTIME_DIR / "agent.sock"

app = typer.Typer(help="CLI for interacting with Access Hub")


def _ensure_runtime_dir() -> Path:
    RUNTIME_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    return RUNTIME_DIR


def _agent_request(payload: dict) -> Optional[dict]:
    _ensure_runtime_dir()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2)
            client.connect(str(SOCKET_PATH))
            message = json.dumps(payload).encode("utf-8") + b"\n"
            client.sendall(message)
            data = b""
            while not data.endswith(b"\n"):
                chunk = client.recv(4096)
                if not chunk:
                    break
                data += chunk
            if not data:
                return None
            return json.loads(data.decode("utf-8").strip())
    except FileNotFoundError:
        return None
    except (ConnectionRefusedError, socket.timeout):
        return None


def _load_token() -> Optional[str]:
    response = _agent_request({"action": "get"})
    if not response:
        return None
    if response.get("status") == "ok":
        return response.get("token")
    if response.get("status") == "expired":
        typer.echo("Session expired. Re-run login.")
        return None
    return None


def _start_agent(token: str, expires_at: float) -> None:
    _ensure_runtime_dir()
    _agent_request({"action": "shutdown"})
    time.sleep(0.05)
    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()
    cmd = [sys.executable, "-m", "cli.agent"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    payload = json.dumps({"token": token, "expires_at": expires_at}) + "\n"
    if proc.stdin:
        proc.stdin.write(payload.encode("utf-8"))
        proc.stdin.flush()
        proc.stdin.close()
    # give the agent a moment to bind the socket
    time.sleep(0.1)


def _save_token(token: str, expires_in: Optional[int]) -> None:
    expires_at = time.time() + (expires_in or 300)
    response = _agent_request({"action": "set", "token": token, "expires_at": expires_at})
    if response and response.get("status") == "ok":
        return
    _start_agent(token, expires_at)


def _mint_capability() -> dict:
    response = _agent_request({"action": "mint_capability"})
    if not response:
        raise RuntimeError("Token broker unavailable")
    if response.get("status") != "ok":
        raise RuntimeError(response.get("message", "unable to mint capability"))
    return response


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
            _save_token(data["access_token"], data.get("expires_in"))
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


@app.command("share-token")
def share_token() -> None:
    """Mint a one-time capability URL that returns the current app token."""

    token = _load_token()
    if not token:
        typer.echo("Not logged in. Run `hub login` first.")
        raise typer.Exit(1)

    try:
        result = _mint_capability()
    except RuntimeError as exc:  # pragma: no cover - defensive path
        typer.echo(str(exc))
        raise typer.Exit(1)

    url = result["url"]
    expiry = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(result["expires_at"]))
    typer.echo("Share this URL with local processes to retrieve the JWT once:")
    typer.echo(f"  {url}")
    typer.echo(f"Capability expires at: {expiry}")


if __name__ == "__main__":
    app()
