# All data is two-dimensional

**Category:** data generation
**Priority:** low
**Status:** open

## Context

Every dataset is 2D, so the cost projections are fitted on 2D grids and extrapolated.

The canonical array layout is `(C, X, Y, Z)` with dimensions dropped right to left, and the
remap, the degradation operators and the vorticity recomputation are all written
dimension-agnostically. The remap is verified on `(3, 16, 8, 4)` in 3D and `(1, 16)` in 1D,
so 3D should need no structural change. This issue records that expectation so it gets
checked rather than assumed.

## What is needed

A 3D dataset, and a run against it.

## Acceptance criteria

A 3D run completes with no code change beyond a dataset config, and the measured cost
matches the projection to within a factor of two.

## Related

`fmeval/remap.py`; `fmeval/data/base.py` for the axis convention.
