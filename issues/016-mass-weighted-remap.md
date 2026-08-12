# Momentum-conserving remap option

**Category:** deferred functionality
**Priority:** low
**Status:** open

## Context

The IN-2 remap averages velocity arithmetically, which conserves velocity rather than
momentum. A strictly momentum-conserving remap would average rho*u and divide by the coarse
density.

Here density varies by under 4%, so the two agree to that order and the arithmetic form is
used. The choice is recorded on every row as `remap_op`, so a run is never ambiguous about
which was applied.

This matters more for a genuinely compressible flow, where density variation is order one --
which is exactly the regime issue 002 is about.

## What is needed

A `conserve: mass_weighted` option on the analysis grid, which needs density available
alongside velocity and must state what it does when density was not requested.

## Acceptance criteria

On a field with strong density variation, the two options differ measurably, and the
mass-weighted form conserves total momentum to machine precision.

## Related

`fmeval/remap.py`; issue 002.
