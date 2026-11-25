"""Run an agent against the fake world, kill it when told, restart it, check."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .check import Verdict, check
from .world import FAULT_KINDS, Fault, World, make_server

PKG_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Task:
    name: str
    prompt: str
    expect: list
    customers: dict = field(default_factory=dict)
    id: str = "task"

    @classmethod
    def load(cls, path: str | Path) -> Task:
        d = json.loads(Path(path).read_text())
        for e in d["expect"]:
            if e["tool"] not in ("charge", "send_email", "write_file"):
                raise ValueError(f"expect entries must be side-effect tools, got {e['tool']!r}")
        return cls(name=d["name"], prompt=d["prompt"], expect=d["expect"],
                   customers=d.get("customers", {}), id=d.get("id", Path(path).stem))


@dataclass
class RunResult:
    fault: Fault | None
    world: World
    attempts: list
    verdict: Verdict

    @property
    def passed(self) -> bool:
        return self.verdict.passed

    def fault_call(self):
        if not self.fault:
            return None
        for c in self.world.calls:
            if c["fault"]:
                return c
        return None

    def to_dict(self) -> dict:
        fc = self.fault_call()
        return {
            "fault": str(self.fault) if self.fault else None,
            "fault_tool": fc["tool"] if fc else None,
            "fault_fired": bool(fc) if self.fault else None,
            "passed": self.passed,
            "problems": self.verdict.problems,
            "attempts": self.attempts,
            "calls": self.world.calls,
            "effects": self.world.effects,
        }


def run(task: Task, cmd: list[str], fault: Fault | None = None, *,
        max_restarts: int = 3, timeout: float = 120.0, env: dict | None = None) -> RunResult:
    world = World(customers=dict(task.customers), fault=fault)
    server = make_server(world)
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    t.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    child_env = os.environ | (env or {}) | {
        "AFTERSHOCK_URL": url,
        "AFTERSHOCK_TASK": task.prompt,
        "AFTERSHOCK_TASK_ID": task.id,
        "PYTHONPATH": os.pathsep.join(filter(None, [str(PKG_ROOT), os.environ.get("PYTHONPATH")])),
    }
    attempts = []
    try:
        for i in range(1, max_restarts + 2):
            world.attempt = i
            p = subprocess.Popen(cmd, env=child_env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True)
            world.proc = p
            try:
                out, _ = p.communicate(timeout=timeout)
                rc = p.returncode
            except subprocess.TimeoutExpired:
                p.kill()
                out, _ = p.communicate()
                rc = "timeout"
            attempts.append({"attempt": i, "exit": rc, "killed": i in world.killed,
                             "output": (out or "")[-2000:]})
            if rc == 0:
                break
    finally:
        server.shutdown()
        server.server_close()
    return RunResult(fault, world, attempts, check(task, world, attempts))


def sweep(task: Task, cmd: list[str], kinds=FAULT_KINDS, *, on_result=None, **kw) -> list[RunResult]:
    """One clean run, then every fault kind at every tool call the clean run made."""
    base = run(task, cmd, None, **kw)
    results = [base]
    if on_result:
        on_result(base)
    n = len(base.world.calls)
    for at in range(1, n + 1):
        for kind in kinds:
            r = run(task, cmd, Fault(kind, at), **kw)
            results.append(r)
            if on_result:
                on_result(r)
    return results
