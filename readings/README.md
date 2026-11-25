# Readings

Each reading is one `aftershock sweep` on the demo invoice task. Each setup has three files:

- `.txt`: the PASS/FAIL lines and summary, as printed
- `.md`: a table, one row per tool call, one column per fault
- `.json`: every call, every effect and the agent's output for each attempt

| File prefix | Model | Setup |
|---|---|---|
| `gemma3-4b-plain` | gemma3 4B | no memory, no warning |
| `gemma3-4b-memory` | gemma3 4B | saves its conversation between restarts |
| `gemma3-4b-careful` | gemma3 4B | told it may have been restarted, and to check first |
| `gemma3-4b-memory-careful` | gemma3 4B | both |

Run on a laptop (Apple M5, 16 GB) through Ollama, temperature 0, one sweep per setup.
