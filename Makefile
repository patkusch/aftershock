.PHONY: install test lint demo

install:
	python -m venv .venv && .venv/bin/pip install -e ".[dev]"

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check .

demo:
	.venv/bin/aftershock demo

.PHONY: double clean

double:
	.venv/bin/aftershock sweep aftershock/demo/invoice.json --double -- .venv/bin/python aftershock/demo/agents/safe.py

clean:
	rm -rf .pytest_cache .ruff_cache *.egg-info
	find . -name __pycache__ -prune -exec rm -rf {} +
