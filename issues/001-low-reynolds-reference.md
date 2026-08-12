# The protocol specifies Re ~ 500; no such dataset exists

**Category:** data generation
**Priority:** medium
**Status:** open

## Context

The evaluation protocol in the metrics document calls for a reference direct numerical
simulation at Re ~ 500, isotropic and doubly periodic. Every doubly-periodic dataset on disk
is Re 5e4 to 1e6:

- `kinet/doubly_periodic/weakly_compressible_isoT_fluids/sys_Re-5e4_Ma-1en1/` (Re = 5e4)
- `.../sys_Re-1e6_Ma-1en1/` (Re = 1e6)
- `kinet/doubly_periodic/old/` (Re = 5e4, 6.25e4, 7.5e4, 8.75e4, 1e5)

So the protocol cannot be executed exactly as written. Nothing in the harness depends on the
Reynolds number, and every measurement taken so far is valid for the flows it was taken on --
but a claim of the form "this metric satisfies the protocol" is not yet available.

## What is needed

Either generate a Re ~ 500 reference, or amend the protocol to the Reynolds numbers we
actually have and record why. The second is cheaper and may be the right answer: at Re = 500
the flow is barely turbulent and several of the failure modes the panel targets would not be
present.

## Acceptance criteria

A dataset config exists for the chosen reference, and the protocol text and the reference
agree.

## Related

The evaluation protocol (IN-3) in the metrics tracker. Issue 002 for the related mismatch.
