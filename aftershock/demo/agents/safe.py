"""Saves progress AND sends a fixed idempotency key with every action.

The key is the same on every restart and every retry, so the service does the
work once and replays its answer after that.
"""

import sys
import time

from aftershock.client import TASK_ID, ToolError, load_state, save_state, tool


def retry(name, key=None, **args):
    for i in range(3):
        try:
            return tool(name, key=key, **args)
        except ToolError as e:
            if e.status < 500 or i == 2:
                raise
            time.sleep(0.05)


state = load_state()
done = state.setdefault("done", {})


def step(name, fn):
    if name in done:
        return done[name]
    out = fn()
    done[name] = out
    save_state(state)
    return out


k = lambda s: f"{TASK_ID}:{s}"
c = step("lookup", lambda: retry("lookup_customer", customer="cus_42"))
step("charge", lambda: retry("charge", key=k("charge"), customer="cus_42", amount=120, description="November"))
step("email", lambda: retry("send_email", key=k("email"), to=c["email"],
                            subject="Your November receipt", body="We charged £120."))
step("file", lambda: retry("write_file", key=k("file"), path="invoices/cus_42-nov.txt",
                           content="cus_42 November £120"))
sys.exit(0)
