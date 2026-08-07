# Gradient quality where L2 goes flat

**Category:** deferred functionality
**Priority:** medium
**Status:** open

## Context

The project's premise is that a pointwise norm stops being informative once a feature is
displaced past its own width. For a metric intended as a *training loss* the relevant question
is not the value but the gradient: does it still point somewhere useful there?

The measurement is the norm of the gradient with respect to the field, against displacement
along the sub-pixel translation axis, with L2 as the control. The registry already carries a
`differentiable` flag, declared rather than inferred, so candidates can be selected.

The displacement scaling measured here makes this concrete and gives a prediction to test.
For small displacement d the error field is d times the gradient of the field, so mean squared
error grows as d^2 and mean absolute error as d^1 -- confirmed to better than 5% over three
doublings. A quadratic metric therefore has a gradient that vanishes linearly as d goes to
zero, while a linear one does not.

## What is needed

A torch or finite-difference path, and one renderer. Torch is already an optional extra
in `pyproject.toml` and is deliberately not a default dependency.

## Acceptance criteria

For a differentiable metric the gradient norm is plotted against displacement, and MSE
reproduces the predicted linear vanishing.

## Related

`differentiable` in `metrics/registry.py`; `degradations/geometric.py`.
