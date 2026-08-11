# Severity ranges should follow each field's spectrum

**Category:** method
**Priority:** high
**Status:** open

## The problem in one sentence

Severity numbers in the config are absolute (a wavenumber, a number of cells), but what a
metric responds to is the *fraction of the field's structure* the operator destroys — and that
fraction depends on where the field keeps its energy, which differs between fields by more than
an order of magnitude.

## Evidence

Measured on the 256² production trajectory at t = 6000 (developed flow). Characteristic scale
is `N` divided by the energy-weighted mean wavenumber:

| field | 50% of energy below | 90% below | 99% below | characteristic scale |
|---|---|---|---|---|
| vorticity | k = 4 | k = 30 | k = 63 | ~29 cells |
| density | k = 1 | k = 3 | k = 6 | ~136 cells |
| velocity | k = 1 | k = 2 | k = 5 | — |

The configured severities are the same for every field: high-pass cutoffs `[2, 4, 8, 16]` and
blur sigmas `[0.5, 1, 2, 4, 8]`. Those land in completely different places on the two fields.

### Symptom 1 — high-pass on density: two of four rungs are the same experiment

Fraction of fluctuation energy removed, and the resulting MSE damage (1.0 = the value two
unrelated fields receive):

| cutoff | vorticity energy removed | vorticity MSE damage | density energy removed | density MSE damage |
|---|---|---|---|---|
| 2 | 0.278 | 0.124 | 0.697 | 0.605 |
| 4 | 0.475 | 0.231 | 0.947 | 0.823 |
| 8 | 0.684 | 0.313 | 0.997 | 0.867 |
| 16 | 0.811 | 0.365 | 1.000 | **0.869** |

On density the energy removed saturates at cutoff 4. Rungs 3 and 4 differ by 0.002 in damage —
they are the same experiment run twice, so the axis has two rungs of information and reports
four. On vorticity the identical cutoffs span 0.278 to 0.811 and behave well.

### Symptom 2 — blur on density: the axis is dead

MSE damage across the configured sigmas:

| sigma | 0.5 | 1 | 2 | 4 | 8 |
|---|---|---|---|---|---|
| vorticity | 0.001 | 0.007 | 0.035 | 0.085 | 0.142 |
| density | 0.000 | 0.000 | 0.000 | 0.001 | **0.012** |

The most severe blur in the config reaches 1.2% of the unrelated-field level on density. A
Gaussian of sigma 8 barely perturbs a field that varies on ~136 cells, so the whole axis carries
almost no signal there — and the acceptance statistics computed from it are being computed from
noise.

So the same fixed list is simultaneously too coarse for high-pass on density (saturating) and
far too fine for blur on density (nothing happens), while being about right for vorticity on
both.

## What this issue is NOT

**It does not explain the MAE / vorticity / high-pass flag, and fixing it will not clear that
flag.** An earlier version of this issue claimed it did. That was wrong, and the correction is
worth recording so nobody fixes this and is then surprised.

On vorticity the high-pass cutoffs are well placed, and MSE is perfectly monotone there
(0.124 → 0.231 → 0.313 → 0.365, rho = 1.0). Only MAE is flat: damage 0.563, 0.499, 0.547, 0.577.
Decomposing `MAE(x, highpass(x)) = <|removed|>` into amplitude and shape shows why:

| cutoff | rms(removed) | `<|removed|>/rms` | product |
|---|---|---|---|
| 2 | 1.275e-3 | 0.820 | 1.045e-3 |
| 4 | 1.738e-3 | 0.533 | 9.262e-4 |
| 8 | 2.021e-3 | 0.502 | 1.015e-3 |
| 16 | 2.184e-3 | 0.490 | 1.071e-3 |

The amplitude rises by a factor 1.71 while the shape factor falls by 0.60, and the two cancel to
within 3%. MSE is a quadratic form, so by Parseval it depends only on the energy removed and
therefore tracks it monotonically. MAE is not, so it also depends on the *shape* of the removed
component's amplitude distribution, which becomes more peaked as more modes enter (0.49 is well
below the Gaussian value of 0.798, i.e. leptokurtic).

That is a genuine property of MAE on this field, not a defect of the axis. No severity
calibration controls it, because the cancellation is between two quantities the severity does
not separately set. Whether it should be reported as a limitation of MAE or investigated further
is a separate question from this issue.

## What is needed

Severity ranges expressed relative to a measured property of each reference field rather than as
absolute constants:

- **spectral axes** — relative to the wavenumber containing a stated fraction of the energy, so
  a cutoff list becomes something like "the k holding 50%, 70%, 85%, 95% of the energy" and lands
  in the same relative place on every field;
- **smoothing axes** — relative to the characteristic scale, so a sigma list is a fraction of it
  rather than a cell count.

That measurement needs the reference field, so it belongs in the pipeline, next to where the
fluctuation RMS is already computed for the relative noise amplitudes. The resolved absolute
severity must still be recorded on every row, or a run stops being interpretable and two runs
stop being comparable.

Note the interaction with issue 031: calibrating severities will also change which rungs reach
saturation, so the two are best looked at together.

## Acceptance criteria

On both density and vorticity, every spectral and smoothing axis shows a monotone ladder in MSE
with adjacent-rung separability above 0.8 and a damage range spanning at least a factor of five,
without hand-tuning the config per field. The resolved severities appear in `results.csv`.

## Related

`degradations/spectral.py`, `degradations/smoothing.py`;
`configs/degradation/default.yaml`; `fmeval/ladder.py` (where the reference RMS is already
measured); issue 031.
