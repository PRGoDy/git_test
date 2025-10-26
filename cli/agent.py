"""In-memory token broker for the Access Hub CLI."""

from __future__ import annotations

import json
import os
import signal
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict

RUNTIME_DIR = Path.home() / ".access-hub"
SOCKET_PATH = RUNTIME_DIR / "agent.sock"


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


def main() -> None:
    payload = sys.stdin.read()
    try:
        initial = json.loads(payload)
    except json.JSONDecodeError:
        return

    token = initial.get("token")
    expires_at = float(initial.get("expires_at", time.time()))

    _ensure_runtime_dir()
    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(SOCKET_PATH))
    os.chmod(str(SOCKET_PATH), 0o600)
    server.listen()

    def handle_exit(signum, frame):  # type: ignore[unused-argument]
        _cleanup()
        server.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    running = True

    while running:
        conn, _ = server.accept()
        with conn:
            request = _read_json(conn)
            action = request.get("action")
            if action == "get":
                if not token:
                    _send_json(conn, {"status": "missing"})
                elif time.time() >= expires_at:
                    _send_json(conn, {"status": "expired"})
                else:
                    _send_json(conn, {"status": "ok", "token": token, "expires_at": expires_at})
            elif action == "set":
                token = request.get("token")
                expires_at = float(request.get("expires_at", time.time()))
                _send_json(conn, {"status": "ok"})
            elif action == "ping":
                _send_json(conn, {"status": "ok"})
            elif action == "shutdown":
                _send_json(conn, {"status": "ok"})
                running = False
            else:
                _send_json(conn, {"status": "error", "message": "unknown action"})

    server.close()


if __name__ == "__main__":
    try:
        main()
    finally:
        _cleanup()
