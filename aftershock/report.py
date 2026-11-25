"""Plain-English and Markdown reports."""

from __future__ import annotations

import json

from .world import FAULT_KINDS, FAULT_MEANING


def _where(r) -> str:
    fired = {c["n"]: c["tool"] for c in r.fault_calls()}
    parts = []
    for f in r.faults:
        tool = fired.get(f.at, "never reached")
        parts.append(f"{f.kind} at call {f.at} ({tool})")
    return " then ".join(parts)


def line(r) -> str:
    head = _where(r) if r.faults else "No fault"
    if r.passed:
        return f"PASS  {head}"
    return f"FAIL  {head}: " + "; ".join(p["text"] for p in r.verdict.problems)


def _hits(r) -> list:
    """What each fault in a run actually hit: (kind, tool, args).

    Call numbers shift after a restart, so two runs are compared by the step a
    fault landed on, not by its number.
    """
    return [(c["fault"], c["tool"], json.dumps(c["args"], sort_keys=True)) for c in r.fault_calls()]


def only_double(results) -> list:
    """Two-fault runs that fail although each fault, alone on the same step, passes."""
    single = {}
    for r in results[1:]:
        if len(r.faults) == 1 and r.all_fired:
            h = _hits(r)[0]
            single[h] = single.get(h, True) and r.passed
    return [r for r in results[1:] if len(r.faults) == 2 and not r.passed
            and all(single.get(h, False) for h in _hits(r))]


def summary(results) -> str:
    base = results[0]
    singles = [r for r in results[1:] if len(r.faults) == 1]
    doubles = [r for r in results[1:] if len(r.faults) == 2]
    out = []
    if not base.passed:
        out.append("The agent fails even without any fault, so the crash results below mean little:")
        out.append("  " + line(base))
    tools = [c["tool"] for c in base.world.calls]
    out.append(f"Clean run made {len(tools)} tool calls: {', '.join(tools) or 'none'}.")
    failed = [r for r in singles if not r.passed]
    out.append(f"{len(singles) - len(failed)} of {len(singles)} crash tests passed.")
    if doubles:
        dfailed = [r for r in doubles if not r.passed]
        out.append(f"{len(doubles) - len(dfailed)} of {len(doubles)} two-fault tests passed.")
    by_kind = {}
    for r in failed:
        by_kind.setdefault(r.fault.kind, []).append(r)
    for kind in FAULT_KINDS:
        if kind in by_kind:
            out.append(f"\nWhen {FAULT_MEANING[kind]}:")
            out.extend("  " + line(r) for r in by_kind[kind])
    if doubles:
        new = only_double(results)
        if new:
            out.append(f"\n{len(new)} failures only show up when two things break (each fault alone, on the same step, passes):")
            out.extend("  " + line(r) for r in new[:10])
            if len(new) > 10:
                out.append(f"  ...and {len(new) - 10} more")
        else:
            out.append("\nNo failure needs two faults to show up: single-fault tests already catch every problem found.")
    if base.passed and not any(not r.passed for r in results[1:]):
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
            r = next((x for x in results[1:] if len(x.faults) == 1
                      and x.fault.at == i and x.fault.kind == kind), None)
            if r is None:
                cells.append("–")
            elif r.passed:
                cells.append("pass")
            else:
                cells.append("**FAIL** " + "; ".join(p["text"] for p in r.verdict.problems))
        rows.append(f"| {i} | {t} | " + " | ".join(cells) + " |")
    singles = [r for r in results[1:] if len(r.faults) == 1]
    failed = sum(not r.passed for r in singles)
    return (f"## {title}\n\nClean run: {'pass' if base.passed else 'FAIL'}. "
            f"Crash tests passed: {len(singles) - failed} of {len(singles)}.\n\n"
            + "\n".join(rows) + "\n")
