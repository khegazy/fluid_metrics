# CRPS and spread-to-skill need ensembles

**Category:** data generation
**Priority:** low
**Status:** open

## Context

Two probabilistic criteria are designed but not applicable. The continuous ranked
probability score reduces to mean absolute error for a deterministic prediction, so it
conveys nothing beyond MAE unless an ensemble or a generative model is available; the
spread-to-skill ratio needs an ensemble by definition. Every dataset here is a single
deterministic realisation.

The metrics document already says to mark these N/A rather than untested, and that is the
current state.

## What is needed

An ensemble of runs at fixed parameters and perturbed initial conditions, or a generative
surrogate that emits a distribution.

If they are implemented, use the correct spread estimator: the average spread must be the
square root of the mean ensemble variance, not the mean of the per-member spreads. Fortin et
al. (2014), J. Hydrometeorology 15(4), 1708, show the naive form is biased low and can turn a
correct verdict of good agreement into a spurious diagnosis of underdispersion.

## Acceptance criteria

An ensemble dataset config exists, and PS-2 and PS-3 produce values that differ from MAE.

## Related

PS-2, PS-3 in `Table_of_Ideas.tex`.
