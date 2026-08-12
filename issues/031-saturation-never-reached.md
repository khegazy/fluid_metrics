# No ladder rung reaches the unrelated-field level

**Category:** method
**Priority:** medium
**Status:** open

## Context

`saturation_level` is undefined for every axis and metric measured so far: nothing on the
ladder reaches 90% of the way from clean to the unrelated-field value. The most severe rung
available is a 16-cell translation, which reaches 0.45 for MSE and 0.68 for MAE on vorticity.

That is honest -- and it means the saturation column carries no information at present, and a
reader could mistake a blank column for a computation that failed.

It also means the ladder spans the informative range but does not bracket it. Whether that
matters depends on the intended use: for ranking models that differ mildly it is fine, and for
characterising a metric's full response it is not.

## What is needed

Either extend the severe end of the ladder -- larger translations, coarsening beyond 16,
noise above 0.5 -- or state in the report that saturation was not reached rather than leaving
the column blank. Probably both.

If the ladder is extended, note that a very large translation approaches the anchor by
construction, so it stops being an independent measurement and starts being a second estimate
of the same quantity.

## Acceptance criteria

Either the saturation column is populated for most axes, or the report states explicitly
that the ladder does not reach saturation and why.

## Related

`saturation_level` in TEST_DESCRIPTION.md; `fmeval/analysis.py`.
