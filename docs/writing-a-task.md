# Writing a task file

A task file is JSON with four parts:

- `name`: a short title for reports
- `prompt`: what the agent is asked to do, passed in `AFTERSHOCK_TASK`
- `customers`: who `lookup_customer` knows about (optional)
- `expect`: every action that should happen exactly once

Each `expect` entry names a tool that changes something (`charge`, `send_email` or `write_file`) and the fields that must match. Numbers match across formats, so `120`, `"120.00"` and `"£120"` are the same. Text matches without caring about capitals.

Add `"repeat_ok": true` for actions that are harmless to repeat, such as saving the same file again.

Anything the agent does that no `expect` entry covers is reported as "did something not asked for".
