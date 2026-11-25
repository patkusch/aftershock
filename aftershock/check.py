"""Compare what the agent actually did with what the task asked for."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Verdict:
    problems: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.problems


def _same(want, got) -> bool:
    try:
        return float(want) == float(str(got).replace("£", "").replace(",", ""))
    except (TypeError, ValueError):
        return str(want).strip().lower() == str(got).strip().lower()


def matches(expect: dict, effect: dict) -> bool:
    if effect["tool"] != expect["tool"]:
        return False
    return all(_same(v, effect["args"].get(k)) for k, v in expect.get("match", {}).items())


def describe(tool: str, args: dict) -> str:
    if tool == "charge":
        amt = args.get("amount")
        return f"charge {args.get('customer')}" + (f" {amt}" if amt is not None else "")
    if tool == "send_email":
        return f"email {args.get('to')}"
    if tool == "write_file":
        return f"write {args.get('path')}"
    return tool


def check(task, world, attempts) -> Verdict:
    v = Verdict()
    used: set = set()
    for exp in task.expect:
        hits = [e for e in world.effects if matches(exp, e)]
        used.update(e["id"] for e in hits)
        what = describe(exp["tool"], exp.get("match", {}))
        if not hits:
            v.problems.append({"kind": "missing", "text": f"never did: {what}"})
        elif len(hits) > 1 and not exp.get("repeat_ok"):
            v.problems.append({"kind": "duplicate",
                               "text": f"did {len(hits)} times, should be once: {what}"})
    for e in world.effects:
        if e["id"] not in used:
            v.problems.append({"kind": "unexpected",
                               "text": f"did something not asked for: {describe(e['tool'], e['args'])}"})
    last = attempts[-1]["exit"] if attempts else None
    if last != 0:
        v.problems.append({"kind": "unfinished",
                           "text": f"never finished (gave up after {len(attempts)} tries)"})
    return v
