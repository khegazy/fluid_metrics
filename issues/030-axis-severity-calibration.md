# Severity ranges should follow each field's spectrum

**Category:** method
**Priority:** high
**Status:** open

## Context

Severity ranges are fixed constants in the config and are applied to every field alike.
That is wrong for the spectral axes, because the informative range depends on where the field
keeps its energy.

Measured on the developed flow, `highpass_ideal` on vorticity: damage 0.566, 0.503, 0.548,
0.580 at cutoffs 2, 4, 8, 16. The rungs are indistinguishable and non-monotone -- a cutoff of 2
already removes almost all the energy, so the remaining rungs add nothing. For MAE on vorticity
this produced rho = 0.40 with a worst frame of -0.80 and a separability of 0.31, which reads as
a defective metric and is in fact a defective axis.

The same argument applies in reverse to the smoothing family: the useful sigma range is set by
the correlation length, which differs between density and vorticity, and between early and late
in the trajectory.

This is the highest-priority method issue because it currently produces flags that point at
the wrong thing.

## What is needed

Severity ranges expressed relative to a measured property of each field rather than as
absolute constants -- for the spectral axes, relative to the wavenumber containing a stated
fraction of the energy; for the smoothing axes, relative to the correlation length.

That measurement belongs in the pipeline, since it needs the reference field, and it must be
recorded on every row so a run remains interpretable.

## Acceptance criteria

On both density and vorticity, every spectral axis shows a monotone ladder with adjacent
separability above 0.8, without hand-tuning the config per field.

## Related

`degradations/spectral.py`; `configs/degradation/default.yaml`; issue 031.
