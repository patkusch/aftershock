# Changelog

## Unreleased

- gemma3 12B readings across the same four setups.

## 0.2.0 (2026-11-25)

- `--double`: try every pair of faults in one run, and name failures that only show up when two things break.
- `--fault` takes several faults, e.g. `crash-after@2,timeout@5`.
- Shell example agent with curl, passes every crash test.
- Guides to the four faults and to writing task files.
- Two-customer example task.
- Security policy, contributing guide, issue templates, Dependabot and tidier CI.

## 0.1.0 (2026-11-25)

- First release: four faults (crash before, crash after, timeout, error), restarts, and checks for duplicate, missing, unexpected and unfinished actions.
- `aftershock demo` with three built-in agents.
- Language-model agent on Ollama, with memory and careful switches.
- First reading: gemma3 4B across four setups.
