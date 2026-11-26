# Words used here

- **Agent**: a program, often driven by a language model, that does a job by calling tools.
- **Tool call**: one request from the agent, such as "charge this customer".
- **Fault**: something aftershock breaks on purpose, on one chosen call.
- **Restart**: running the agent again after it crashed, as a supervisor would.
- **Sweep**: one clean run, then a run for every fault at every call.
- **Duplicate**: an action that should happen once happened more than once.
- **Idempotency key**: a fixed label on an action, so repeating it does nothing new.
- **Reading**: a saved sweep of a real model, kept in `readings/`.
