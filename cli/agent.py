"""In-memory token broker for the Access Hub CLI.

The broker stores the authenticated Access Hub session entirely in memory and
exposes two access patterns:

* A Unix domain socket used by the CLI to retrieve or update the cached JWT.
* An ephemeral loopback HTTP endpoint guarded by one-time capability tokens so
  that GUI processes (e.g. browsers) can fetch the same JWT without it ever
  touching disk.

Both surfaces run in the same short-lived process and share the same in-memory
token state. Capability tokens expire quickly (default 60 seconds) and are
deleted after the first successful use so other processes cannot linger on the
credential.
"""

from __future__ import annotations

import json
import os
import secrets
import signal
import socket
import struct
import sys
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

RUNTIME_DIR = Path.home() / ".access-hub"
SOCKET_PATH = RUNTIME_DIR / "agent.sock"
CAPABILITY_TTL_SECONDS = 60


@dataclass
class BrokerState:
    token: Optional[str] = None
    expires_at: float = 0.0
    http_port: int = 0
    capabilities: Dict[str, float] = None  # cap -> expiry

    def __post_init__(self) -> None:
        if self.capabilities is None:
            self.capabilities = {}


STATE = BrokerState()


def _ensure_runtime_dir() -> Path:
    RUNTIME_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    return RUNTIME_DIR


def _read_json(conn: socket.socket) -> Dict[str, Any]:
    data = b""
    while not data.endswith(b"\n"):
        chunk = conn.recv(4096)
        if not chunk:
            break
        data += chunk
    if not data:
        return {}
    return json.loads(data.decode("utf-8").strip())


def _send_json(conn: socket.socket, payload: Dict[str, Any]) -> None:
    message = json.dumps(payload).encode("utf-8") + b"\n"
    conn.sendall(message)


def _cleanup() -> None:
    try:
        SOCKET_PATH.unlink()
    except FileNotFoundError:
        pass


def _is_same_user(conn: socket.socket) -> bool:
    """Validate that the connecting process is running as the same OS user."""

    # macOS/BSD provide getpeereid() on AF_UNIX sockets.
    if hasattr(conn, "getpeereid"):
        uid, _gid = conn.getpeereid()
        return uid == os.getuid()

    # Linux exposes SO_PEERCRED for the same purpose.
    if sys.platform.startswith("linux"):
        try:
            creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.pack("iii", 0, 0, 0))
        except OSError:
            return False
        pid, uid, _gid = struct.unpack("iii", creds)
        return uid == os.getuid() and pid > 0

    # On unsupported platforms we fail closed to avoid weakening guarantees.
    return False


class _TokenHandler(BaseHTTPRequestHandler):
    server_version = "AccessHubBroker/1.0"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        if parsed.path != "/token":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        params = parse_qs(parsed.query)
        capability = params.get("cap", [None])[0]
        if not capability:
            self.send_error(HTTPStatus.BAD_REQUEST, "missing capability")
            return

        expiry = STATE.capabilities.pop(capability, 0)
        now = time.time()
        if not expiry or expiry < now:
            self.send_error(HTTPStatus.FORBIDDEN, "invalid capability")
            return

        if not STATE.token or STATE.expires_at <= now:
            self.send_error(HTTPStatus.FORBIDDEN, "token unavailable")
            return

        body = json.dumps({"token": STATE.token, "expires_at": STATE.expires_at}).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - inherited name
        # Suppress default stdout logging to keep the broker quiet.
        return


def _start_http_server() -> HTTPServer:
    httpd = HTTPServer(("127.0.0.1", 0), _TokenHandler)
    STATE.http_port = httpd.server_port

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def main() -> None:
    payload = sys.stdin.read()
    try:
        initial = json.loads(payload)
    except json.JSONDecodeError:
        return

    STATE.token = initial.get("token")
    STATE.expires_at = float(initial.get("expires_at", time.time()))

    _ensure_runtime_dir()
    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(SOCKET_PATH))
    os.chmod(str(SOCKET_PATH), 0o600)
    server.listen()

    httpd = _start_http_server()

    def handle_exit(signum, frame):  # type: ignore[unused-argument]
        _cleanup()
        httpd.shutdown()
        httpd.server_close()
        server.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    running = True

    while running:
        conn, _ = server.accept()
        with conn:
            if not _is_same_user(conn):
                _send_json(conn, {"status": "error", "message": "unauthorized"})
                continue
            request = _read_json(conn)
            action = request.get("action")
            if action == "get":
                if not STATE.token:
                    _send_json(conn, {"status": "missing"})
                elif time.time() >= STATE.expires_at:
                    _send_json(conn, {"status": "expired"})
                else:
                    _send_json(conn, {"status": "ok", "token": STATE.token, "expires_at": STATE.expires_at})
            elif action == "set":
                STATE.token = request.get("token")
                STATE.expires_at = float(request.get("expires_at", time.time()))
                _send_json(conn, {"status": "ok"})
            elif action == "ping":
                _send_json(conn, {"status": "ok"})
            elif action == "mint_capability":
                if not STATE.token or STATE.expires_at <= time.time():
                    _send_json(conn, {"status": "error", "message": "token unavailable"})
                else:
                    capability = secrets.token_urlsafe(32)
                    expiry = time.time() + CAPABILITY_TTL_SECONDS
                    STATE.capabilities[capability] = expiry
                    url = f"http://127.0.0.1:{STATE.http_port}/token?cap={capability}"
                    _send_json(conn, {"status": "ok", "url": url, "expires_at": expiry})
            elif action == "shutdown":
                _send_json(conn, {"status": "ok"})
                running = False
            else:
                _send_json(conn, {"status": "error", "message": "unknown action"})

    httpd.shutdown()
    httpd.server_close()
    server.close()


if __name__ == "__main__":
    try:
        main()
    finally:
        _cleanup()
