# Examples

| File | What it shows |
|---|---|
| `curl_agent.sh` | An agent in plain shell with curl. It sends idempotency keys and passes every crash test. |
| `two-customers.json` | A harder task: two customers, six actions that should each happen once. |

Run the shell agent:

```bash
aftershock sweep aftershock/demo/invoice.json -- sh examples/curl_agent.sh
```
