"""The fake world an agent acts on: payments, email and files, all recorded.

Every tool call goes through `World.call`, which is also where faults are
injected. A fault fires once, on a chosen call number, counted across all
restarts of the agent.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Tools that change the world. Calling one of these twice is the bug we hunt.
SIDE_EFFECTS = {"charge", "send_email", "write_file"}
# Tools that only look. Safe to repeat.
READS = {"lookup_customer", "find_charges", "find_emails", "read_file"}
TOOLS = SIDE_EFFECTS | READS

REQUIRED = {
    "lookup_customer": ["customer"],
    "find_charges": ["customer"],
    "find_emails": ["to"],
    "read_file": ["path"],
    "charge": ["customer", "amount"],
    "send_email": ["to", "subject"],
    "write_file": ["path", "content"],
}

FAULT_KINDS = ("crash-before", "crash-after", "timeout", "error")

FAULT_MEANING = {
    "crash-before": "the agent was killed just before the call reached the service",
    "crash-after": "the service did the work, then the agent was killed before it heard back",
    "timeout": "the service did the work, but the agent was told the call timed out",
    "error": "the service refused the call once with a temporary error",
}


@dataclass(frozen=True)
class Fault:
    kind: str
    at: int  # 1-based tool call number

    def __post_init__(self) -> None:
        if self.kind not in FAULT_KINDS:
            raise ValueError(f"unknown fault {self.kind!r}; pick one of {', '.join(FAULT_KINDS)}")
        if self.at < 1:
            raise ValueError("fault call number starts at 1")

    @classmethod
    def parse(cls, text: str) -> Fault:
        """Read 'crash-after@3' into Fault('crash-after', 3)."""
        kind, _, at = text.partition("@")
        if not at.isdigit():
            raise ValueError(f"write faults as kind@call, e.g. crash-after@3 (got {text!r})")
        return cls(kind, int(at))

    def __str__(self) -> str:
        return f"{self.kind}@{self.at}"


@dataclass
class World:
    customers: dict = field(default_factory=dict)
    fault: Fault | None = None
    calls: list = field(default_factory=list)
    effects: list = field(default_factory=list)
    state: dict = field(default_factory=dict)
    files: dict = field(default_factory=dict)
    attempt: int = 0
    proc: object = None
    killed: set = field(default_factory=set)  # attempt numbers we killed
    fired: bool = False

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: dict = {}

    # -- the one entry point -------------------------------------------------
    def call(self, tool: str, args: dict, key: str | None):
        """Return (status, body, kill_agent)."""
        with self._lock:
            n = len(self.calls) + 1
            fault = None
            if self.fault and not self.fired and self.fault.at == n:
                fault, self.fired = self.fault, True
            rec = {
                "n": n,
                "attempt": self.attempt,
                "tool": tool,
                "args": args,
                "key": key,
                "applied": False,
                "replayed": False,
                "fault": fault.kind if fault else None,
            }
            self.calls.append(rec)

            if fault and fault.kind == "crash-before":
                return None, None, True
            if fault and fault.kind == "error":
                return 503, {"error": "service unavailable, try again"}, False

            if tool not in TOOLS:
                return 404, {"error": f"no tool called {tool!r}"}, False
            missing = [k for k in REQUIRED[tool] if args.get(k) in (None, "")]
            if missing:
                return 400, {"error": f"missing {', '.join(missing)}"}, False

            if key and (tool, key) in self._keys:
                result = self._keys[(tool, key)]
                rec["replayed"] = True
            else:
                result = self._apply(tool, args, n)
                rec["applied"] = tool in SIDE_EFFECTS
                if key:
                    self._keys[(tool, key)] = result

            if fault and fault.kind == "crash-after":
                return None, None, True
            if fault and fault.kind == "timeout":
                return 504, {"error": "request timed out"}, False
            return 200, result, False

    def kill_agent(self) -> None:
        self.killed.add(self.attempt)
        if self.proc is not None:
            try:
                self.proc.kill()
            except ProcessLookupError:
                pass

    # -- the services --------------------------------------------------------
    def _apply(self, tool: str, a: dict, n: int):
        if tool == "lookup_customer":
            c = self.customers.get(a["customer"])
            return c if c else {"error": "no such customer"}
        if tool == "find_charges":
            return {"charges": [e["args"] | {"id": e["id"]} for e in self.effects
                                if e["tool"] == "charge" and e["args"].get("customer") == a["customer"]]}
        if tool == "find_emails":
            return {"emails": [e["args"] | {"id": e["id"]} for e in self.effects
                               if e["tool"] == "send_email" and e["args"].get("to") == a["to"]]}
        if tool == "read_file":
            if a["path"] in self.files:
                return {"content": self.files[a["path"]]}
            return {"error": "no such file"}
        prefix = {"charge": "ch", "send_email": "em", "write_file": "fi"}[tool]
        eid = f"{prefix}_{len(self.effects) + 1}"
        if tool == "write_file":
            self.files[a["path"]] = a["content"]
        self.effects.append({"id": eid, "tool": tool, "args": dict(a), "call": n, "attempt": self.attempt})
        return {"ok": True, "id": eid}


def make_server(world: World) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):  # keep output clean
            pass

        def _send(self, status: int, body) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return None
            return body if isinstance(body, dict) else None

        def do_GET(self):
            if self.path == "/state":
                return self._send(200, world.state)
            if self.path == "/health":
                return self._send(200, {"ok": True})
            self._send(404, {"error": "not found"})

        def do_PUT(self):
            if self.path != "/state":
                return self._send(404, {"error": "not found"})
            body = self._body()
            if body is None:
                return self._send(400, {"error": "send a JSON object"})
            world.state = body
            self._send(200, {"ok": True})

        def do_POST(self):
            if not self.path.startswith("/tool/"):
                return self._send(404, {"error": "not found"})
            body = self._body()
            if body is None:
                return self._send(400, {"error": "send a JSON object"})
            status, result, kill = world.call(self.path[6:], body, self.headers.get("Idempotency-Key"))
            if kill:
                world.kill_agent()
                self.close_connection = True
                return  # the agent never hears back
            self._send(status, result)

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)
