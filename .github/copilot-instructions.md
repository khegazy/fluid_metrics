# Copilot instructions

The full instructions for working in this repository are in [`AGENTS.md`](../AGENTS.md) at the
repository root. Read it before changing anything; it is the canonical file and this one is
only a pointer, so that the two cannot drift apart.

It covers how to add a metric, a degradation, a data source, and a figure or table; how to
write tests here; how to treat the generated LaTeX; and a table of traps that have already
caught someone, each of which would quietly corrupt results.

Two rules worth repeating because they are easy to violate by accident:

- **Verify before claiming.** `pytest | tail` masks the exit code, so a `&&` chain passes with
  failing tests. Use
  `uv run pytest -q > /tmp/pt.txt 2>&1; RC=$?; tail -3 /tmp/pt.txt; [ $RC -eq 0 ] || exit 1`.
- **Never hand-edit anything under `results/`.** It is generated. Fix the renderer and re-run
  `make_report.py`.
