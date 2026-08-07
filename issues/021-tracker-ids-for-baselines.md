# `NM-0` is the reserved identifier for the pointwise baselines

**Category:** technical debt
**Priority:** —
**Status:** RESOLVED (2026-08-07) — accepted

## Decision

`NM-0` is accepted as the identifier for the pointwise baseline controls: MAE, MSE, RMSE and
NRMSE. It is now a real slot rather than a placeholder, and result CSVs carrying it are
correct.

## Context

MAE, MSE, RMSE and NRMSE are tagged `tracker_id = "NM-0"`. The identifier did not originate in
`Table_of_Ideas.tex` — it was introduced here as a reserved slot for pointwise baseline
controls, on the grounds that these are not candidate metrics but the control the candidates
must beat. The identifier lands in every result row and every provenance snapshot, so it
needed blessing before it spread through the CSVs.

`PH-4` on enstrophy and kinetic energy was taken from the document and was never in question.

## Remaining action

Add `NM-0` to the master table in `Table_of_Ideas.tex` so the document and the code agree, with
a note that it denotes the pointwise baseline family rather than a candidate metric. Until that
happens, someone reading the document alone will not find the identifier that appears in every
result file.

## Related

`metrics/standard_ml.py`; the master table in `Table_of_Ideas.tex`.
