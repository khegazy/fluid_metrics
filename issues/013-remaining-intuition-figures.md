# Outlier, invariance and triangle-inequality figures

**Category:** deferred functionality
**Priority:** low
**Status:** open

## Context

Three criteria are designed but have no figure, so they are currently only describable in
prose rather than checkable at a glance.

- **Outlier response.** Inject a single-cell spike and measure it. The concentration
  statistic is the right companion: measured, a one-cell translation puts 20.6% of the total
  MSE in the top 1% of cells against a structureless-noise baseline of 8.5%.
- **Invariance audit.** Apply a transformation to *both* fields that physics says should not
  change the score -- a 90-degree rotation, a reflection, a joint translation. Any departure is
  a bug or a documented limitation.
- **Metric axioms.** A scatter of d(a,c) against d(a,b) + d(b,c) with the y = x line; points
  above it are triangle-inequality violations. Failing is acceptable for a diagnostic and
  disqualifying for a loss, so the point is to know.

## What is needed

Three renderers, plus the probe configuration to generate the inputs. Each is a config
flag and one function in `analysis.py`, so they can land individually.

## Acceptance criteria

Each figure renders and skips cleanly when its probe was not run.

## Related

`configs/report/default.yaml`; `fmeval/report/plots.py`.
