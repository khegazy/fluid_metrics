# Solenoidal projection for the spectral operators

**Category:** deferred functionality
**Priority:** low
**Status:** open

## Context

Every spectral operator applied per channel to a velocity field breaks the divergence
constraint. At Ma = 0.1 that is acceptable and arguably makes the probe harder, but it means
the damage measured on a velocity field mixes "lost small scales" with "gained spurious
divergence", and the two cannot be separated.

A Leray projection after the filter would isolate the effect. kinet has no such function to
borrow -- only divergence-free *synthesis* in its homogeneous-isotropic-turbulence initial
conditions -- so this has to be written against the vendored wavenumber grid.

## What is needed

A projection helper and a `project_solenoidal` option on the spectral operators, off by
default so the harder probe remains the default.

## Acceptance criteria

With the option on, the divergence of a filtered velocity field is at machine precision,
and the damage differs measurably from the unprojected case.

## Related

`degradations/spectral.py`; `fmeval/external/kinet_spectral.py` for the wavenumber grid.
