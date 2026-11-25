# Notes for coding agents

- Standard library only in `aftershock/`. Test tools live in the `dev` extra.
- Run `.venv/bin/pytest -q` and `.venv/bin/ruff check .` before every commit, and commit only if both exit 0.
- Every new fault or check needs one agent that fails it and one that passes it, in `tests/`.
- Readings in `readings/` are real runs. Never edit them by hand.
- Write README text in plain English: what it does and why.
