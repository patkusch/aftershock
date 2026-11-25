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
    faults: tuple
    world: World
    attempts: list
    verdict: Verdict

    @property
    def passed(self) -> bool:
        return self.verdict.passed

    @property
    def fault(self):
        """The first fault, or None. Single-fault runs have only this one."""
        return self.faults[0] if self.faults else None

    def fault_calls(self) -> list:
        """The calls where a fault fired, in order."""
        return [c for c in self.world.calls if c["fault"]]

    @property
    def all_fired(self) -> bool:
        return len(self.fault_calls()) == len(self.faults)

    def to_dict(self) -> dict:
        return {
            "faults": [str(f) for f in self.faults],
            "fault_tools": [c["tool"] for c in self.fault_calls()],
            "all_fired": self.all_fired,
            "passed": self.passed,
            "problems": self.verdict.problems,
            "attempts": self.attempts,
            "calls": self.world.calls,
            "effects": self.world.effects,
        }


def run(task: Task, cmd: list[str], faults=None, *,
        max_restarts: int = 3, timeout: float = 120.0, env: dict | None = None) -> RunResult:
    if faults is None:
        faults = ()
    elif isinstance(faults, Fault):
        faults = (faults,)
    faults = tuple(sorted(faults, key=lambda f: f.at))
    world = World(customers=dict(task.customers), faults=faults)
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
    return RunResult(faults, world, attempts, check(task, world, attempts))


def plan(n: int, kinds=FAULT_KINDS, double: bool = False) -> list[tuple]:
    """Which fault sets to try, given a clean run of n calls.

    Single: every kind at every call. Double adds pairs: every kind at every
    call, then every kind again at each of the next n calls. The restarted agent keeps
    counting from where it stopped, so the second fault can land on the redo.
    """
    singles = [(Fault(k, at),) for at in range(1, n + 1) for k in kinds]
    if not double:
        return singles
    return singles + [(Fault(k1, i), Fault(k2, j))
                      for i in range(1, n + 1) for k1 in kinds
                      for j in range(i + 1, i + n + 1) for k2 in kinds]


def sweep(task: Task, cmd: list[str], kinds=FAULT_KINDS, *, double: bool = False,
          on_result=None, **kw) -> list[RunResult]:
    """One clean run, then every fault set from `plan`.

    In a double sweep, runs where the agent finished before the second fault
    could fire are dropped, because they repeat a single-fault test.
    """
    base = run(task, cmd, None, **kw)
    results = [base]
    if on_result:
        on_result(base)
    for faults in plan(len(base.world.calls), kinds, double):
        r = run(task, cmd, faults, **kw)
        if len(faults) > 1 and not r.all_fired:
            continue
        results.append(r)
        if on_result:
            on_result(r)
    return results
