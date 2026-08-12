# Rotation, which must rotate vector components

**Category:** deferred functionality
**Priority:** low
**Status:** open

## Context

Rotation was deliberately left out of the geometric family. It is not simply a resampling
of the grid: a rotated velocity field must have its *components* rotated too, and forgetting
that produces a field that looks entirely plausible and is physically wrong -- the flow would
point in the wrong direction relative to its own structures.

It is a useful probe for an isotropic flow, where a rotation of both fields should leave any
metric unchanged, which makes it the natural basis for the invariance audit.

## What is needed

An operator that rotates the grid and applies the corresponding rotation to any vector
field's components, using the field's declared channel count to know which fields are vectors.
Only multiples of 90 degrees are exact on a Cartesian grid; anything else needs interpolation
and introduces smoothing that would confound the probe.

## Acceptance criteria

Rotating a velocity field by 90 degrees and rotating back reproduces the original exactly,
and the rotated field's divergence matches the original's.

## Related

`degradations/geometric.py`; issue 013 for the invariance audit.
