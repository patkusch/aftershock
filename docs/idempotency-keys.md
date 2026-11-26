# Adding idempotency keys to your agent

An idempotency key is a fixed label sent with an action. If the same label
arrives twice, the service does the work once and sends back the first answer.
This is the only fix aftershock has found for a lost reply.

The rule: **the key must be the same on every retry and every restart.** So
build it from things that do not change, such as the task and the step, never
from the time or a random number.

```python
from aftershock.client import TASK_ID, tool

tool("charge", key=f"{TASK_ID}:charge", customer="cus_42", amount=120)
```

Over plain HTTP, send it as a header:

```bash
curl -X POST "$AFTERSHOCK_URL/tool/charge" \
  -H "Idempotency-Key: invoice-nov:charge" \
  -H "Content-Type: application/json" \
  -d '{"customer": "cus_42", "amount": 120}'
```

Real payment and email providers often accept the same header. Check that
yours does before relying on it, and keep the key for as long as a retry could
happen.

If a language model chooses the actions, do not ask it to invent keys. Add
them in your own code, around the tool call.
