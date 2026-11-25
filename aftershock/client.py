"""Tiny helper for Python agents. Agents in other languages just speak HTTP:

    POST $AFTERSHOCK_URL/tool/<name>   JSON args, optional Idempotency-Key header
    GET  $AFTERSHOCK_URL/state         the agent's own saved memory
    PUT  $AFTERSHOCK_URL/state         replace that memory
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

URL = os.environ.get("AFTERSHOCK_URL", "http://127.0.0.1:8765")
TASK = os.environ.get("AFTERSHOCK_TASK", "")
TASK_ID = os.environ.get("AFTERSHOCK_TASK_ID", "task")


class ToolError(Exception):
    def __init__(self, status: int, body: dict):
        super().__init__(f"{status}: {body.get('error', body)}")
        self.status, self.body = status, body


def _req(method: str, path: str, body=None, key: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(URL + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("Idempotency-Key", key)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise ToolError(e.code, json.loads(e.read() or b"{}")) from None


def tool(name: str, key: str | None = None, **args):
    return _req("POST", f"/tool/{name}", args, key)


def load_state() -> dict:
    return _req("GET", "/state")


def save_state(state: dict) -> None:
    _req("PUT", "/state", state)
