# Severity ranges should follow each field's spectrum

**Category:** method
**Priority:** high
**Status:** fixed 2026-08-11 (`create_harness`)

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

## What was done, and what it measured

Severities on those axes are now **relative**, and the pipeline resolves them per field against a
spectrum it measures from the data (`fmeval/calibration.py`). Smoothing widths are a fraction of
the field's characteristic scale; filter cutoffs are the fraction of fluctuation energy the filter
removes, with the operator declaring which side of the cutoff it removes. Both the nominal and the
resolved absolute severity are on every row, the measurement is written to `data/calibration.csv`,
and it is measured once per (field, analysis grid) rather than per frame — re-measuring per frame
would make the ladder drift as the flow evolves and the per-frame rank correlation would then be
comparing different ladders.

Measured on 15 frames of the production trajectory from t = 5000, on density and vorticity:

| axis | vorticity: rungs, damage range | density: rungs, damage range |
|---|---|---|
| `gaussian_blur` | 4, 62x | 4, 617x |
| `box_blur` | 4, 24x | 4, 265x |
| `median_blur` | 3, 27x | 3, 82x |
| `lowpass_ideal` | 4, 10x | 3, 17x |
| `lowpass_butterworth` | 4, 11x | 4, 14x |
| `highpass_ideal` | 4, 3.4x | 2, 1.1x |
| `highpass_butterworth` | 4, 3.1x | 2, 1.1x |

Every one of these is monotone in MSE with a per-frame Spearman of exactly 1.0 and a monotone
fraction of 1.0, on both fields, from one config that names no field. The old behaviour it
replaces: the blur axis reached 1.2% of the unrelated-field level on density and carried no signal,
and the high-pass cutoffs saturated by the second rung there so two of four rungs were the same
experiment.

**Three problems surfaced only once this was measured, and each was a real defect:**

1. **The low-pass mapping was inverted.** "Fraction removed" was fed to a function returning "the
   wavenumber below which that fraction lies", so a request to remove 5% resolved to k = 1 and
   removed 95%. Damage then *fell* with severity. The two sides are now separate declarations
   (`energy_above` / `energy_below`) precisely because getting this wrong leaves every number
   plausible.
2. **Even-width rounding was displacing the field.** A calibrated width of 3.2 cells rounds to an
   even window, which has no centre cell and is therefore placed asymmetrically — a half-cell
   shift. On a project whose central concern is that metrics over-punish displacement, that
   dominated: vorticity damage ran 0.0121, 0.0041, 0.0338, 0.0880, non-monotone. The windowed
   kernels now round to odd widths.
3. **A rung can resolve to something that is not an experiment.** Either it lands on the same
   quantised severity as a milder rung, or it lands where the operator does nothing at all. Both
   are now detected, recorded per row as `severity_degenerate`, excluded from the statistics, and
   named in the run log. Left uncounted they do not merely pad the ladder: a repeat makes the rank
   correlation score a tie as agreement and makes separability compare a distribution against
   itself, and a no-op contributes an exactly-zero damage that made one axis appear to span eleven
   orders of magnitude.

### A fourth defect, found by reporting the realised removal

Adding the realised energy removal to the report immediately exposed one more, and it was the worst
of the four because every number it produced looked reasonable. **There were two definitions of
wavenumber magnitude and they disagreed.** The spectral operators compared a continuous `|k|`
against their cutoff, while the calibration binned energy into shells of `rint(|k|)`; the diagonal
modes therefore fell on opposite sides of the same number, since `(1, 1)` has `|k| = 1.414` and
belongs to shell 1.

On density that is not a rounding nuisance, because its fluctuation energy is almost entirely in
those diagonal modes. A low-pass asked to remove 30% removed 99.997%:

| field | axis | requested | realised, before | realised, after |
|---|---|---|---|---|
| density | `lowpass_ideal` | 0.05 / 0.15 / 0.30 | 0.057 / 0.176 / **1.000** | 0.057 / 0.175 / 0.303 |
| vorticity | `lowpass_ideal` | 0.05 / 0.15 / 0.30 / 0.45 | 0.049 / 0.157 / 0.307 / 0.495 | 0.048 / 0.150 / 0.298 / 0.451 |

There is now one definition, in `fmeval/wavenumbers.py`, used by both sides, and the calibration
curve is tabulated at the exact magnitudes present on the grid rather than at integer shells. The
requested and realised fractions now agree to within a few percent wherever the spectrum can
resolve the request.

The same measurement also replaced the duplicate-rung detection. It had been based on each operator
*declaring* how it rounds its severity, which is a declaration that can be wrong and which was
wrong for the sharp filters (they were declared as rounding to integer shells). Two rungs performing
the same operation produce a bitwise identical field and therefore an exactly equal
`energy_changed`, so the repeat is now detected by measurement and no declaration is needed.

One case is deliberately **not** excluded: a cutoff can be distinct from its neighbours and still be
far from the fraction requested, because it must land on an available set of modes. That is a valid
experiment whose nominal severity misdescribes it, so the report names it rather than dropping it.
Measured, one density low-pass rung asks to remove 45% and removes 99.997%, and the mildest sharp
high-pass rung on density asks for 45% and removes 3e-5.

## Two limits that calibration does not remove

**Sharp filters cannot resolve four rungs on density.** Its fluctuation energy is 69% in the four
diagonal modes at |k| = √2, only 3e-5 in the axis modes at |k| = 1 just below them, and 88% by
|k| = 3. Two consecutive available cutoffs therefore differ by most of the field, so a sharp ladder
on density has at most two or three distinct rungs however the config is written. The Butterworth
pair rolls off smoothly and does resolve four, which is a second reason to keep both rather than
treating the smooth filter only as a ringing control.

**The high-pass axis does not reach the factor-five damage range, on either field.** It is squeezed
from both sides: below the k = 1 floor the filter passes every mode and the rung is a no-op, and
above it the damage is already most of the way to an unrelated field. The configured window is the
widest measured — 3.4x on vorticity, two usable rungs on density. This is a property of these
fields' bottom-heavy spectra, not of the severity list, and a field with more energy at high
wavenumbers would not have it. **So the acceptance criterion above is met on every axis except
high-pass, where it is not achievable on this data.** Recorded here rather than quietly narrowing
the criterion.

One cost worth knowing: because the calibration is measured from the frames actually evaluated,
changing `dataset.time.reduction` moves the resolved severities by about 5e-6 relative. Runs at
different reductions were already not directly comparable, so this adds no new restriction, but it
does mean the exact reduction-invariance the seeding gives is not available on a calibrated axis.

Also surfaced: `scale_spread` for vorticity on this trajectory is 21–33% depending on the span,
above the 0.25 warning threshold. A single calibration is genuinely questionable for that field
over a long window, and the run now says so instead of averaging over it silently.

## Related

`degradations/spectral.py`, `degradations/smoothing.py`;
`configs/degradation/default.yaml`; `fmeval/ladder.py` (where the reference RMS is already
measured); issue 031.
