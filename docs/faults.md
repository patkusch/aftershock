# The four faults

Each fault is placed on one tool call, counted from the start of the run.

| Fault | The service | The agent | Bug it finds |
|---|---|---|---|
| `crash-before` | did nothing | is killed | redoing earlier steps after a restart |
| `crash-after` | did the work | is killed before the reply | repeating an action whose reply was lost |
| `timeout` | did the work | is told it timed out | retrying an action that already worked |
| `error` | did nothing, says "try again" | gets an error | giving up, or claiming success anyway |

`crash-after` and `timeout` are the hardest to pass. Saving progress does not help, because the agent never learned the action worked. Only an idempotency key does.
