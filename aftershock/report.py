"""Plain-English and Markdown reports."""

from __future__ import annotations

from .world import FAULT_KINDS, FAULT_MEANING


def line(r) -> str:
    if r.fault is None:
        head = "No fault"
    else:
        fc = r.fault_call()
        where = f"call {r.fault.at} ({fc['tool']})" if fc else f"call {r.fault.at} (never reached)"
        head = f"{r.fault.kind} at {where}"
    if r.passed:
        return f"PASS  {head}"
    return f"FAIL  {head}: " + "; ".join(p["text"] for p in r.verdict.problems)


def summary(results) -> str:
    base, faulted = results[0], results[1:]
    failed = [r for r in faulted if not r.passed]
    out = []
    if not base.passed:
        out.append("The agent fails even without any fault, so the crash results below mean little:")
        out.append("  " + line(base))
    tools = [c["tool"] for c in base.world.calls]
    out.append(f"Clean run made {len(tools)} tool calls: {', '.join(tools) or 'none'}.")
    out.append(f"{len(faulted) - len(failed)} of {len(faulted)} crash tests passed.")
    by_kind = {}
    for r in failed:
        by_kind.setdefault(r.fault.kind, []).append(r)
    for kind in FAULT_KINDS:
        if kind in by_kind:
            out.append(f"\nWhen {FAULT_MEANING[kind]}:")
            out.extend("  " + line(r) for r in by_kind[kind])
    if not failed and base.passed:
        out.append("Every action happened exactly once, whatever broke.")
    return "\n".join(out)


def markdown(results, title: str) -> str:
    base = results[0]
    tools = [c["tool"] for c in base.world.calls]
    rows = ["| Call | Tool | " + " | ".join(FAULT_KINDS) + " |",
            "|---|---|" + "---|" * len(FAULT_KINDS)]
    for i, t in enumerate(tools, 1):
        cells = []
        for kind in FAULT_KINDS:
            r = next((x for x in results[1:] if x.fault.at == i and x.fault.kind == kind), None)
            if r is None:
                cells.append("–")
            elif r.passed:
                cells.append("pass")
            else:
                cells.append("**FAIL** " + "; ".join(p["text"] for p in r.verdict.problems))
        rows.append(f"| {i} | {t} | " + " | ".join(cells) + " |")
    failed = sum(not r.passed for r in results[1:])
    return (f"## {title}\n\nClean run: {'pass' if base.passed else 'FAIL'}. "
            f"Crash tests passed: {len(results) - 1 - failed} of {len(results) - 1}.\n\n"
            + "\n".join(rows) + "\n")
