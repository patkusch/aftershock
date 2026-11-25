"""aftershock: crash-test an agent and check it never does anything twice."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .report import line, markdown, summary
from .runner import Task, run, sweep
from .world import FAULT_KINDS, Fault

DEMO = Path(__file__).parent / "demo"
DEMO_AGENTS = [
    ("naive", "does each step, remembers nothing"),
    ("resumes", "saves progress, skips finished steps"),
    ("safe", "saves progress and sends idempotency keys"),
]


def _split(argv):
    if "--" not in argv:
        return argv, []
    i = argv.index("--")
    return argv[:i], argv[i + 1:]


def _kinds(text):
    kinds = [k.strip() for k in text.split(",") if k.strip()]
    bad = [k for k in kinds if k not in FAULT_KINDS]
    if bad:
        raise SystemExit(f"unknown fault kind(s): {', '.join(bad)}. Pick from {', '.join(FAULT_KINDS)}")
    return kinds


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    own, cmd = _split(argv)
    p = argparse.ArgumentParser(prog="aftershock", description=__doc__)
    p.add_argument("--version", action="version", version=f"aftershock {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    pr = sub.add_parser("run", help="run once, optionally with one fault: aftershock run TASK --fault crash-after@2 -- CMD")
    pr.add_argument("task")
    pr.add_argument("--fault", help="kind@call, e.g. crash-after@2")

    ps = sub.add_parser("sweep", help="try every fault at every call: aftershock sweep TASK -- CMD")
    ps.add_argument("task")
    ps.add_argument("--faults", default=",".join(FAULT_KINDS), help="comma list of fault kinds")
    ps.add_argument("--json", help="write full results here")
    ps.add_argument("--md", help="write a Markdown table here")

    sub.add_parser("demo", help="sweep the three built-in agents (no model, no key)")

    for sp in (pr, ps):
        sp.add_argument("--restarts", type=int, default=3, help="restarts allowed after a crash (default 3)")
        sp.add_argument("--timeout", type=float, default=120, help="seconds per attempt (default 120)")

    a = p.parse_args(own)

    if a.command == "demo":
        task = Task.load(DEMO / "invoice.json")
        print(f"Task: {task.prompt}\n")
        for name, what in DEMO_AGENTS:
            res = sweep(task, [sys.executable, str(DEMO / "agents" / f"{name}.py")], timeout=30)
            failed = sum(not r.passed for r in res[1:])
            print(f"== {name}: {what}")
            print(f"   {len(res) - 1 - failed} of {len(res) - 1} crash tests passed")
            for r in [r for r in res if not r.passed][:3]:
                print("   " + line(r))
            print()
        return 0

    if not cmd:
        p.error("give the agent command after --, e.g. -- python my_agent.py")
    try:
        task = Task.load(a.task)
    except (OSError, ValueError, KeyError) as e:
        print(f"could not read task {a.task}: {e}", file=sys.stderr)
        return 2
    kw = {"max_restarts": a.restarts, "timeout": a.timeout}

    if a.command == "run":
        try:
            fault = Fault.parse(a.fault) if a.fault else None
        except ValueError as e:
            print(e, file=sys.stderr)
            return 2
        r = run(task, cmd, fault, **kw)
        print(line(r))
        for at in r.attempts:
            print(f"  attempt {at['attempt']}: exit {at['exit']}" + (" (we killed it)" if at["killed"] else ""))
        return 0 if r.passed else 1

    res = sweep(task, cmd, _kinds(a.faults), on_result=lambda r: print(line(r), flush=True), **kw)
    print()
    print(summary(res))
    if a.json:
        Path(a.json).write_text(json.dumps([r.to_dict() for r in res], indent=2))
    if a.md:
        Path(a.md).write_text(markdown(res, task.name))
    return 0 if all(r.passed for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
