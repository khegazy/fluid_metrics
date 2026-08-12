# Read the real prediction/target pairs

**Category:** deferred functionality
**Priority:** high
**Status:** open

## Context

The degradation ladder is a proxy. Blur, translation and noise are *hypotheses* about how
a surrogate fails. A metric can be monotone on all eleven axes and still be useless on an
autoregressive rollout that accumulates energy at the grid scale, because that failure mode
is not on the ladder.

Real prediction/target pairs already exist on disk:
`datasets/results/entropic_D2Q9/<run>/forecast_t0-*.h5`, organised by variable group with
`pred_<step>` and `target_<step>` keys at 500-step intervals, `u` already shaped
`(2, 256, 256)`. Run names encode a coarsening ladder (`..._from_256_to128`, `..._to_64`).

The ladder decides what to *reject*; real forecasts decide what to *trust*. No metric should
be described as trustworthy before this lands.

## What is needed

A reader in `fmeval/data/forecast.py`. It differs in kind from the existing readers: it
supplies a *pair* rather than a single trajectory, so it should expose two Trajectory objects
over a shared time axis, and the pipeline gains one branch that compares prediction against
target instead of building a ladder. Roughly 40 lines plus the branch.

## Acceptance criteria

A dataset config points at a forecast run, an evaluation produces rows whose
`degradation` is the model rather than a synthetic operator, and the report renders.

## Related

`fmeval/data/base.py` for the Trajectory contract; `fmeval/pipeline.py`.
