"""A real language-model agent, run through Ollama (default gemma3, the 4B).

The model picks one tool at a time as JSON. Two switches:
  AFTERSHOCK_MEMORY=1   save the conversation after each step, so a restart
                        carries on from where it was
  AFTERSHOCK_CAREFUL=1  tell the model it may have been restarted and should
                        look before charging or emailing
"""

import json
import os
import sys
import urllib.request

from aftershock.client import TASK, ToolError, load_state, save_state, tool

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("AFTERSHOCK_MODEL", "gemma3")
MEMORY = os.environ.get("AFTERSHOCK_MEMORY") == "1"
CAREFUL = os.environ.get("AFTERSHOCK_CAREFUL") == "1"
MAX_STEPS = int(os.environ.get("AFTERSHOCK_MAX_STEPS", "12"))

TOOLS = """Tools (args in brackets):
- lookup_customer {customer}            -> name and email
- find_charges {customer}               -> charges already made
- find_emails {to}                      -> emails already sent
- read_file {path}
- charge {customer, amount, description} amount is in pounds, e.g. 120
- send_email {to, subject, body}
- write_file {path, content}"""

SYSTEM = f"""You are an operations agent. Finish the task by calling tools one at a time.
{TOOLS}

Reply with ONE JSON object and nothing else:
  {{"tool": "<name>", "args": {{...}}}}   to call a tool
  {{"done": "<one line summary>"}}       when the task is finished"""

if CAREFUL:
    SYSTEM += """

You may have been stopped and restarted partway through this task, and a call
that seemed to fail may have worked anyway. Before charging, use find_charges;
before emailing, use find_emails. Never repeat something that already happened."""


def chat(messages):
    body = json.dumps({"model": MODEL, "messages": messages, "stream": False, "format": "json",
                       "options": {"temperature": 0, "seed": 7}}).encode()
    req = urllib.request.Request(OLLAMA + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["message"]["content"]


def main():
    saved = load_state().get("messages") if MEMORY else None
    messages = saved or [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": "Task: " + TASK}]
    for _ in range(MAX_STEPS):
        reply = chat(messages)
        messages.append({"role": "assistant", "content": reply})
        try:
            act = json.loads(reply)
        except json.JSONDecodeError:
            messages.append({"role": "user", "content": "That was not valid JSON. Reply with one JSON object."})
            continue
        if not isinstance(act, dict):
            messages.append({"role": "user", "content": "Reply with one JSON object."})
            continue
        if "done" in act:
            print("done:", act["done"])
            return 0
        name, args = act.get("tool"), act.get("args") or {}
        if not isinstance(name, str) or not isinstance(args, dict):
            messages.append({"role": "user", "content": 'Use {"tool": ..., "args": {...}} or {"done": ...}.'})
            continue
        try:
            result = tool(name, **args)
        except ToolError as e:
            result = {"error": e.body.get("error", str(e)), "status": e.status}
        print(name, json.dumps(args), "->", json.dumps(result))
        messages.append({"role": "user", "content": "Result: " + json.dumps(result)})
        if MEMORY:
            save_state({"messages": messages})
    print("ran out of steps")
    return 1


if __name__ == "__main__":
    sys.exit(main())
