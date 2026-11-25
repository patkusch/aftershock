# aftershock

[![ci](https://github.com/patkusch/aftershock/actions/workflows/ci.yml/badge.svg)](https://github.com/patkusch/aftershock/actions/workflows/ci.yml) ![python](https://img.shields.io/badge/python-3.10%2B-blue) ![deps](https://img.shields.io/badge/dependencies-none-brightgreen) ![licence](https://img.shields.io/badge/licence-MIT-lightgrey)

**Crash-test your agent. Find out if it charges the customer twice.**

Agents crash, time out and get restarted. When that happens partway through a
job, many agents redo work they already did: a second payment, a second email,
a second refund. aftershock finds those moments before your customers do.

It runs your agent against a fake payments, email and file service. Then it
breaks things on purpose, one call at a time, restarts the agent and checks
what really happened.

```
$ aftershock demo

== naive: does each step, remembers nothing
   9 of 16 crash tests passed
   FAIL  crash-after at call 2 (charge): did 2 times, should be once: charge cus_42 120

== resumes: saves progress, skips finished steps
   12 of 16 crash tests passed
   FAIL  crash-after at call 2 (charge): did 2 times, should be once: charge cus_42 120

== safe: saves progress and sends idempotency keys
   16 of 16 crash tests passed
```

No model and no API key needed for the demo. No dependencies beyond Python 3.10+.

## Why saving progress is not enough

The middle agent above saves its progress after every step, which is what most
"durable" agents do. It still double-charges. The payment went through, but
the agent was killed before it heard back, so it never marked the step done.
On restart it charges again.

The fix is an **idempotency key**: a fixed label sent with each action, the
same on every retry and restart. The service sees the label, knows it already
did that job, and sends back the earlier answer instead of charging again. The
third agent does this and passes every test.

## What it breaks

aftershock first runs your agent once with nothing broken, and counts its tool
calls. Then, for every call, it tries each of these:

| Fault | What happens |
|---|---|
| `crash-before` | The agent is killed just before the call reaches the service. Nothing happened yet. |
| `crash-after` | The service does the work, then the agent is killed before it hears back. |
| `timeout` | The service does the work, but tells the agent the call timed out. |
| `error` | The service refuses the call once with a "try again" error. |

After each crash it restarts the agent (up to 3 times) and checks:

- **duplicate**: something that should happen once happened more than once
- **missing**: something the task asked for never happened
- **unexpected**: the agent did something nobody asked for
- **unfinished**: the agent never completed the job

## Who it is for

- People building agents that pay, email, book or write things on someone's behalf.
- Teams adding retries or restarts to an agent and wanting proof it is safe.
- Anyone comparing agent frameworks or models on what happens when things break.

## Use it on your own agent

```bash
pip install git+https://github.com/patkusch/aftershock
aftershock sweep my_task.json -- python my_agent.py
```

It exits 0 when every test passes and 1 when any fails, so it can gate CI.
Add `--md report.md` for a table or `--json results.json` for every call and
effect. To try one fault: `aftershock run my_task.json --fault crash-after@2 -- python my_agent.py`.

Your agent can be written in any language. It reads two settings from its
environment, `AFTERSHOCK_URL` and `AFTERSHOCK_TASK`, and talks plain HTTP:

| Request | What it does |
|---|---|
| `POST /tool/<name>` with JSON args | Calls a tool. Add an `Idempotency-Key` header to make retries safe. |
| `GET /state` / `PUT /state` | The agent's own saved memory. It survives restarts, like a database would. |

Tools: `charge`, `send_email`, `write_file` change things. `lookup_customer`,
`find_charges`, `find_emails`, `read_file` only look. Python agents can use
the small helper in [`aftershock/client.py`](aftershock/client.py). For a non-Python example, [`examples/curl_agent.sh`](examples/curl_agent.sh)
does the whole job in shell with curl and passes every test.

A task file says what should happen, once each:

```json
{
  "name": "Bill a customer for November",
  "prompt": "Charge cus_42 £120, email them a receipt, save the invoice.",
  "customers": {"cus_42": {"customer": "cus_42", "email": "ana@example.com"}},
  "expect": [
    {"tool": "charge", "match": {"customer": "cus_42", "amount": 120}},
    {"tool": "send_email", "match": {"to": "ana@example.com"}},
    {"tool": "write_file", "match": {"path": "invoices/cus_42-nov.txt"}, "repeat_ok": true}
  ]
}
```

`repeat_ok` is for actions that are harmless to repeat, like saving the same file again.

## A real language-model agent

[`aftershock/demo/agents/llm.py`](aftershock/demo/agents/llm.py) is a small
agent that runs on a local model through [Ollama](https://ollama.com)
(gemma3 by default; set `AFTERSHOCK_MODEL` to change it). It has two switches:
`AFTERSHOCK_MEMORY=1` saves the conversation so a restart carries on, and
`AFTERSHOCK_CAREFUL=1` tells the model it may have been restarted and should
check before charging or emailing.

```bash
aftershock sweep aftershock/demo/invoice.json -- python aftershock/demo/agents/llm.py
```

### First reading: gemma3 4B (25 Nov 2026)

One sweep per setup on the invoice task, run on a laptop. The careful agent makes
two extra "look first" calls, so it gets more tests.

| Setup | Crash tests passed |
|---|---|
| Plain | 8 of 16 (50%) |
| Saves its conversation (`MEMORY`) | 11 of 16 (69%) |
| Told to check before acting (`CAREFUL`) | 15 of 24 (63%) |
| Both | 20 of 24 (83%) |

What the logs show:

- **No setup was safe.** Even with both switches on, a lost reply after the
  payment still charged the customer twice. Only idempotency keys fix that,
  and the model cannot add those itself.
- **It said it charged when it hadn't.** When the payment service said "try
  again", the model moved on, emailed the receipt, and finished with "Invoice
  created and payment processed". No money was taken.
- **It looked, then charged anyway.** In careful mode, after a restart, it
  checked past charges, saw the November charge was already there, and
  charged again.
- **Some passes were luck.** On a timeout the model ignored the error and moved
  on. That passed only because the payment had in fact gone through.

Full results, one file per setup, are in [`readings/`](readings/).


## Questions

**Do I still need this if I use a durable workflow tool?** Yes. Those tools restart your agent; they cannot know whether your payment call already went through. aftershock checks that the restart is actually safe.

**Does it call real services?** No. Everything runs on your machine against fake services that record what happened.

## Limits

- The services are fake. aftershock tests how your agent behaves, not how your real payment provider does.
- One fault per run. Two crashes in a row are not tested yet.
- A fault is placed by call number, so an agent that makes different calls each run (common with language models) can be hit at different places from one run to the next.

## More

- [The four faults](docs/faults.md)
- [Writing a task file](docs/writing-a-task.md)
- [Readings](readings/)
- [Changelog](CHANGELOG.md)

## Licence

MIT
