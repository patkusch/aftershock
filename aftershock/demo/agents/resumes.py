"""Saves progress after each step and skips finished steps on restart.

This is what most "durable" agents do. It still double-charges when the
service did the work but the agent never heard back, because the step was
never marked done.
"""

import sys
import time

from aftershock.client import ToolError, load_state, save_state, tool


def retry(name, **args):
    for i in range(3):
        try:
            return tool(name, **args)
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


c = step("lookup", lambda: retry("lookup_customer", customer="cus_42"))
step("charge", lambda: retry("charge", customer="cus_42", amount=120, description="November"))
step("email", lambda: retry("send_email", to=c["email"], subject="Your November receipt", body="We charged £120."))
step("file", lambda: retry("write_file", path="invoices/cus_42-nov.txt", content="cus_42 November £120"))
sys.exit(0)
