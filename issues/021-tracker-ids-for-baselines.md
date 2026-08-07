# `NM-0` for the L^p baselines is invented

**Category:** technical debt
**Priority:** decide early
**Status:** open

## Context

MAE, MSE, RMSE and NRMSE are tagged `tracker_id = "NM-0"`. **That identifier is not in
`Table_of_Ideas.tex`.** I invented it as a reserved slot for pointwise baseline controls,
because these are not candidate metrics -- they are the control the candidates must beat.

The identifier lands in every result row and in every provenance snapshot, so it will spread
through the CSVs quickly. Worth blessing or correcting before that happens rather than after.

`PH-4` on enstrophy and kinetic energy is taken from the document and is not in question.

## What is needed

A decision: keep `NM-0`, use a different reserved identifier, or leave the baselines
untagged with an empty identifier.

## Acceptance criteria

The identifier in `metrics/standard_ml.py` matches whatever the metrics document says, and
the document is updated if a new slot was created.

## Related

`metrics/standard_ml.py`; the master table in `Table_of_Ideas.tex`.
