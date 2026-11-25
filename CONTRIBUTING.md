# Contributing

Bug reports and small pull requests are welcome.

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q
.venv/bin/ruff check .
```

New faults or checks need a test that shows an agent failing them and an agent passing them. Keep the core free of dependencies: standard library only.
