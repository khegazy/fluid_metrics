# No shocklet-populated compressible turbulence

**Category:** data generation
**Priority:** high
**Status:** open — accepted, scheduled (2026-08-07)

## Context

The stated north-star case is many small shocks embedded in turbulence. The current target
dataset does not contain them: `weakly_compressible_isoT_fluids` at Ma = 0.1 has density
varying by under 4% and no shocks at all. Measured on a frame at t = 5000, density spans
0.9612 to 1.0065.

Shocked data exists elsewhere in the tree -- `kinet/sod/compressible_fluids/` and
`flow_around_objects/compressible_fluids/` -- but those are a Riemann problem and an
obstacle flow, not a doubly-periodic shocklet field.

Consequence: the shock-oriented metrics (SH-1 shock detector, SH-2 surface distances, PH-1
entropy production) have nothing valid to be validated against. The harness will run on
shocked data unchanged, so this is a data gap and not a code gap.

## Decision

Accepted 2026-08-07: shock datasets will be added later. The shock-oriented metrics are
therefore *deferred* rather than blocked, and the harness needs no change to accommodate them —
it is format-agnostic and will run on shocked data unchanged. Until such a dataset exists, do
not report SH-1, SH-2 or PH-1 as validated.

## What is needed

Generate a doubly-periodic compressible turbulence run at a Mach number high enough to
produce eddy shocklets. Lee, Lele and Moin (1991), Physics of Fluids A 3(4), 657, is the
reference case for this regime.

## Acceptance criteria

A dataset config exists whose density field contains identifiable shocks, and a shock
detector run on it returns a non-trivial mask.

## Related

SH-1, SH-2, PH-1 in `Table_of_Ideas.tex`. Issue 001.
