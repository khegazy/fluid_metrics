# What the suite measures

A reference for every quantity the evaluation reports, written for someone who has not read
the code. Open this when a table column says `separability_auc_min = 0.62` and you need to
know what that means and whether to care.

**The suite measures; it does not decide.** Every number below is a measurement. Where a
reference threshold appears it only populates a `flags` column so a row can be found
quickly — it never labels a metric accepted or rejected. That judgement is ours to make.

A copy of this file sits in every run folder, so a results directory explains its own
numbers even after it has been sent to someone else.

## How the measurement works

We have one trusted simulation and no model predictions, so the thing to compare against is
manufactured. The reference field is damaged in controlled steps, and each candidate metric
is asked to score the damaged versions against the original.

**Rung.** One damaged version of the reference. Rung 0 is the reference itself, so any
pairwise error metric must return exactly zero there.

**Axis.** One family of rungs sharing a single severity knob — for instance Gaussian blur at
sigma = 0.5, 1, 2, 4, 8. An axis is *the unit of rank correlation*. Blur at sigma = 2 and a
4-cell translation have no order relative to one another, and neither do Gaussian blur and
median blur even though both smooth, so correlations are never computed across axes.

**Severity direction.** Some knobs get worse as they grow (blur sigma) and some as they
shrink (a low-pass cutoff). Each operator declares which, and the rungs are sorted into
increasing-damage order before numbering, so a cutoff list written `[64, 32, 16, 8]` gets the
right ordinal levels rather than a perfectly inverted ladder.

**Damage, written D.** Raw mean squared error and a raw transport distance are not
comparable, so every value is also reported on a shared dimensionless scale:

    D = (value - clean) / (unrelated - clean)

`clean` is the reference value and `unrelated` is *measured*, not assumed. D = 0 is a perfect
match and D = 1 is what the metric gives two fields that share every statistic but no
positional alignment. A ratio to the clean value would not work, because mean squared error
is exactly zero there.

**Analysis grid (IN-2).** Both fields are placed on a common grid before measurement, by
conservative block averaging. Derived fields are **recomputed** on that grid rather than
averaged: vorticity is the curl of velocity, so averaging it would give a field that is not
the vorticity of the velocity beside it. Measured, the difference between recomputing and
averaging is 5.6% / 18.3% / 25.9% at coarsening factors 2 / 4 / 8 — not a rounding detail.

**Why so many numbers per axis.** A metric can be monotone and still useless: if adjacent
rungs overlap across frames it cannot rank two models one step apart. It can be monotone and
still uninformative: if it saturates at rung 1 it has no resolution in the interesting
regime. Each quantity below closes one of those gaps.

---

## Group A: does the metric respond correctly?

### `rho`

**What it is.** How reliably the metric orders the rungs of one axis from mildest to worst.
1.0 means it gets the order right every time, 0 means no relationship, -1 means it is exactly
backwards.

**How it is computed.** Spearman rank correlation between the rung number and the metric
value, computed **within each frame separately**, then the median over frames is reported.

**Why not pooled over frames.** Because that measures the wrong thing. The flow evolves along
the trajectory, and on this data the density perturbation grows six orders of magnitude from
start to end. Pooling every frame together means the worst rung early is numerically smaller
than the mildest rung late, so the correlation collapses even when the ordering is perfect
inside every single frame. Measured: every density axis was perfectly ordered within every
frame while the pooled value read between 0.10 and 0.91 depending on the axis. Per-frame is
the statistic that answers the question actually being asked.

**Range.** -1 to 1, dimensionless.

**Good and bad.** 1.0 is what a well-behaved metric gives on a well-behaved axis; most of our
baselines achieve it on most axes. Below about 0.9, look at `rho_frame_min` and at the axis
itself before blaming the metric — a common cause is an axis with no dynamic range rather
than a defective metric.

**Why we report it.** This is the core requirement: a metric used for model selection must
not rank a worse model as better. A non-monotone metric is worse than no metric, because
optimising against it moves in the wrong direction.

**Caveats.** With only four or five rungs the per-frame value takes a small discrete set of
values, so the median over frames is coarse. It says nothing about *how much* the metric
changes — see `sensitivity_level` and the damage columns for that.

**Where it appears.** `axis_detail__field-*.csv`; the heatmap figure; `rho_min` in the
summary.

### `rho_frame_min`

**What it is.** The worst per-frame value behind `rho`. If `rho` is 1.0 but this is -0.8, the
metric orders the rungs correctly on most frames and gets them badly wrong on at least one.

**Why we report it.** A median hides a tail. On our data MAE on vorticity had `rho = 0.40`
with `rho_frame_min = -0.8` on the high-pass axis, and that tail is what identified the
problem as an unusable axis rather than a marginal one.

**Where it appears.** `axis_detail__field-*.csv`.

### `rho_pooled`

**What it is.** The rank correlation computed by pooling every frame together, which is the
statistic we deliberately do *not* use as primary. Kept for comparison only.

**How to read it.** A large gap between `rho` and `rho_pooled` indicates a **non-stationary
field** — one whose overall amplitude is changing along the trajectory — not a defective
metric. If they agree, the field is roughly stationary over the frames sampled.

**Where it appears.** `axis_detail__field-*.csv`; `rho_pooled_min` in the summary.

### `rho_ci_lo`, `rho_ci_hi`

**What they are.** A 5th-95th percentile interval on `rho`, showing how much the value would
move on a different sample of frames.

**How they are computed.** A moving-block bootstrap over frames: contiguous blocks of frames
are resampled and the per-frame median recomputed. **Blocks, not individual frames**, because
a metric's value evolves smoothly in time and is therefore autocorrelated; resampling frames
independently would treat correlated samples as independent and produce an interval far too
narrow to be honest.

**Caveats.** Undefined when there are fewer than twice the block length in frames, which
shows as `--`. The block length should reflect the decorrelation time of the flow and is
currently a configured constant, not measured from the data.

**Where they appear.** `axis_detail__field-*.csv`.

### `monotone_fraction`

**What it is.** The fraction of frames on which the rungs are ordered *strictly* correctly,
with no ties or inversions anywhere in the ladder.

**Range.** 0 to 1. 1.0 means every frame was perfect.

**Good and bad.** This is stricter than `rho`, which tolerates a single swap. Read the two
together: high `rho` with a low `monotone_fraction` means the metric usually gets the overall
trend right but often muddles a neighbouring pair.

**Where it appears.** `axis_detail__field-*.csv`; `monotone_fraction_min` in the summary.

### `separability_auc_min`

**What it is.** Whether the metric can actually tell two *neighbouring* rungs apart, given how
much its value scatters from frame to frame. The smallest such separation across all adjacent
pairs on the axis.

**How it is computed.** For each adjacent pair of rungs, the Mann-Whitney U statistic divided
by the product of the sample sizes — the probability that a randomly chosen frame from the
worse rung scores worse than a randomly chosen frame from the milder rung. The minimum over
pairs is reported.

**Range.** 0 to 1. 0.5 means the two rungs' distributions are indistinguishable; 1.0 means
they never overlap.

**Good and bad.** Above 0.8 the metric can rank models one rung apart with confidence. Around
0.5 it cannot, no matter how clean the median curve looks — which is exactly the failure a
monotonicity number alone would hide.

**Why we report it.** Monotone medians are not enough. If you intend to select between two
models that differ by roughly one rung's worth of quality, this number tells you whether the
metric can see the difference at all.

**Caveats.** **Deliberately reported without a p-value.** The metric trace is autocorrelated
in time, so any test assuming independent samples would be strongly anti-conservative and
would report spurious significance. Treat this purely as a descriptive overlap measure. It
also needs a reasonable number of frames; with ten or twenty it is noisy.

**Where it appears.** `axis_detail__field-*.csv`; `separability_auc_min` in the summary.

### `sensitivity_level`

**What it is.** The first rung at which the metric has moved 10% of the way from its clean
value to the unrelated-field value. In short: how early does it start complaining?

**How it is computed.** The lowest rung whose median value reaches `clean + 0.10 * span`,
where `span` is the **shared** clean-to-unrelated range rather than the axis's own maximum.
Using each axis's own range would make an axis that barely damages the field look just as
sensitive as one that destroys it, so the numbers would not be comparable between rows.

The 10% fraction is fixed once in the code and is never tuned per metric — otherwise the
quantity becomes something one can adjust until the answer is pleasing.

**Range.** An integer rung number, or `--` when the threshold is never reached.

**Good and bad.** Lower is more sensitive, but earlier is not automatically better: a metric
that fires at rung 1 on every axis may simply be noisy. Read it against the `field_gallery`
figure, which shows what each rung actually looks like — a metric that first complains only
after the field is visibly ruined is not earning its place.

**Where it appears.** `axis_detail__field-*.csv`; `sensitivity_level_median` in the summary.

### `saturation_level`

**What it is.** The first rung at which the metric has used up 90% of its range — beyond which
it can no longer distinguish worse from much worse.

**Range.** An integer rung, or `--` if never reached, which is the common case and is
informative in itself: it means nothing on the ladder is as damaging as full decorrelation.

**Good and bad.** Saturating at rung 1 is the quantitative form of the double-penalty
complaint: the metric reports "as bad as possible" for damage that is in fact mild, so it
cannot rank anything above that point.

**Where it appears.** `axis_detail__field-*.csv`; `saturation_level_median` in the summary.

---

## Group B: can it be fooled?

Two fields are constructed specifically to mislead. They probe different weaknesses, and
neither is a rung on any axis, so both are excluded from every rank correlation.

### `gaussian_impostor_value`, `gaussian_impostor_damage`

**What it is.** The metric's response to a field that has the reference's energy spectrum
*exactly* and none of its structure. This is the IN-4 check.

**How the field is built.** Every Fourier amplitude of the reference is kept and every phase
is replaced with that of a white Gaussian field. Consequences, all verified: the energy
spectrum and the two-point correlation are identical to machine precision (relative difference
about 1e-17); the variance is preserved; and the flatness collapses from about 17 to 3.0, the
Gaussian value. It is not turbulence.

**Range.** `_damage` is on the shared D scale, so 0 means indistinguishable from the reference
and 1 means as different as an unrelated field.

**Good and bad.** A value near **0 is a failure**: it means the metric cannot tell real
turbulence from a Gaussian field with the same spectrum, so it is responding only to
second-order statistics.

**What it actually catches.** Not the L^p family. Measured, mean squared error gives this field
0.51-0.80 depending on the field — it rejects it firmly, because a phase-randomised field is
pointwise uncorrelated with the reference. The check is aimed at metrics whose entire content
is the amplitude spectrum: an energy spectrum (BD-1) or a two-point correlation (BD-2) scores
it as **perfect**. Until such metrics are implemented this column will look uninformative, and
a report in which every metric passes should not be read as reassuring.

**Caveats.** Values above 1 are possible and have been observed (MAE on vorticity, 1.38),
meaning the metric judges the Gaussian field worse than a genuinely unrelated turbulent field.
A plausible mechanism is that real vorticity is intermittent, so two independent turbulent
fields share large quiet regions where the difference is small, while a Gaussian field of
matched variance has none — but this is conjecture and has not been tested.

**Where they appear.** `deception_table.csv`; the deception figure; the summary.

### `gaussian_impostor_nearest_rung`

**What it is.** The ordinary rung whose damage is closest to the Gaussian field's, which is
what makes the damage figure interpretable. An entry of `translate_x=16` reads: *this metric
considers the Gaussian field about as bad as displacing the reference by 16 cells.*

**Where it appears.** `deception_table.csv`.

### `uncorrelated_value`, `uncorrelated_damage`

**What it is.** The value the metric gives two fields with identical statistics and no
positional alignment. This is the anchor that defines D = 1, so `uncorrelated_damage` reads
exactly 1.000 by construction and serves as a consistency check rather than a result.

**How it is measured.** The reference is translated by a large random offset, drawn from the
middle half of each axis. On a periodic domain a translation preserves every single- and
multi-point statistic *exactly*, so this is a perfect statistical twin — verified as a variance
ratio of 1.000000 and a flatness matching the reference to three decimals. Several independent
draws are averaged; six draws agreed within 0.96-1.03 on the real data.

**Why not a distant frame of the same trajectory.** Tested, and it fails. The flow decays: from
t = 5000 to t = 9000 the vorticity variance falls to 0.70 of its value and the flatness rises
from 17.1 to 27.3. That is a different physical state, not a twin, and it scores *closer* to
the reference than a true twin does purely because the field has weakened.

**Caveats.** Translation only decorrelates a **broadband** field. For a field dominated by a
single large-scale mode the residual correlation after translation is cos(2 pi d / L), which no
offset makes reliably small, so the anchor would be biased and would swing between draws. Real
turbulence is broadband and this is not a concern here, but the spread across draws is the
diagnostic — if it is wide, do not trust the anchor for that field.

**Where they appear.** `deception_table.csv`; `results.csv` under `degradation = uncorrelated`.

---

## Group C: is it worth a panel slot?

### `cost_s`, `median`, `p95`

**What it is.** Wall-clock seconds for a single metric evaluation on one field and one variant.
Times the metric call only — reading the data and building the degraded variants are excluded,
so this is the metric's own cost.

**Good and bad.** Nothing here is absolute; the useful comparison is against other metrics and
against the projection below.

**Where they appear.** `cost_table.csv`; `cost_s` in the summary.

### `per_frame_s`, `full_trajectory_s`

**What it is.** The cost scaled up: `per_frame_s` is one evaluation times the number of
variants in the ladder, and `full_trajectory_s` projects that to all 10001 frames.

**Why we report it.** This is the number that decides usability. A metric that takes a second
per evaluation is fine as an occasional diagnostic and impossible inside a training loop, and
the raw per-call figure does not make that obvious.

**Caveats.** A linear projection, so it ignores any caching or vectorisation a real
implementation might exploit, and it assumes the present ladder width.

**Where they appear.** `cost_table.csv`.

### `cost_relative`, `relative`

**What it is.** Cost divided by the cheapest metric in the same run, so 2.0 means twice the
cost of the cheapest thing measured.

**Caveats.** The baseline is whatever happened to be cheapest in *this* run, so the number is
not comparable between runs with different metric sets.

**Where they appear.** `cost_table.csv`; `cost_relative` in the summary.

### The redundancy matrix

**What it is.** Rank correlation between every pair of metrics across the whole ladder. Two
metrics that correlate near 1 are near-duplicates and one of them is a wasted panel slot.

**How it is computed.** One observation per (axis, rung), using the median over frames — which
is the level at which the panel decision is actually made. The **reference rung is excluded**:
every pairwise error metric is exactly zero there, so keeping it would add a point all metrics
share by construction and pull every correlation toward +1.

**Range.** -1 to 1. The configured reference for "redundant" is 0.95.

**Caveats, and an important one.** High rank correlation means the metrics *order* the
degradations the same way. It does **not** mean they weight them the same. Measured on our
data, MAE and MSE correlate at 0.995 across the ladder, yet MAE assigns 55 times the damage
MSE does at an eighth of a cell of displacement, because one is linear and the other quadratic
in the displacement. For selecting between models by ranking they are duplicates; as training
losses they are not. Read this matrix alongside the displacement figure, never alone.

**Where it appears.** `redundancy_table.csv`, in the comparison folder only, since it needs at
least two metrics.

### The selectivity profile

**What it is.** One metric's `rho` across every axis, read as a row rather than a column: a
fingerprint of *what that metric detects*.

**How to read it.** Two metrics with near-identical profiles are redundant even when their
magnitudes differ. A profile that is uniform across every axis indicates a metric responding to
damage in general rather than to any specific failure mode, which makes it a poor diagnostic
even if it is perfectly monotone.

**Where it appears.** The selectivity figure and the heatmap — the same numbers, read in the two
directions.

---

## Normalisation and bookkeeping

### `value`

The metric's raw output, in whatever units it declares. Not comparable between metrics; use
`damage` for that.

### `damage`

`value` on the shared dimensionless scale described above. 0 is a perfect match, 1 is an
unrelated field. This is the only quantity that can be compared across metrics with different
units.

### `value_clean`

The metric's value on the reference rung, the median over frames. Exactly 0 for any pairwise
error metric — a nonzero entry means a bug.

### `value_min`, `value_max`

The smallest and largest values the metric took on that axis, for a quick sense of its working
range before any normalisation.

### `value_uncorrelated`, `span`

`value_uncorrelated` is the measured unrelated-field anchor, and `span` is
`value_uncorrelated - value_clean`: the metric's full working range, and the denominator of the
damage score.

### `anchor_source`

Where the unrelated-field anchor came from. `uncorrelated` means it was measured properly.
Anything ending in `@max` means the ladder had no anchor entry and the largest configured
translation was used instead, which **understates** it — a 16-cell displacement reaches only
about 0.6 of the true value on this data, so damage scores would be inflated by roughly 1.6x.
If you see `@max`, add the `uncorrelated` entry to the ladder and re-run.

### `degenerate`

True when the metric has essentially no dynamic range on that field — its clean and unrelated
values are indistinguishable — so damage cannot be computed and every normalised quantity is
suppressed. The `flags` column reads `no dynamic range`.

**This is expected for single-field metrics, and is not a bug.** A single-field metric
characterises one field rather than comparing two, and the unrelated-field anchor is the
reference *translated*, which leaves every statistic unchanged. So enstrophy — or any other
single-field quantity — has exactly the same value on the reference and on the anchor, the span
is zero, and there is nothing to normalise against. `enstrophy` will therefore appear in the
summary with `rho = -1`, `no dynamic range`, and no damage figure, on its very first run.

Read that as the suite telling you something true: enstrophy cannot serve as a comparison
metric between two fields. It is a tripwire on a single field, which is how it is intended.
`rho = -1` is also correct rather than alarming: smoothing destroys small-scale structure, so
enstrophy *falls* monotonically as damage increases, and a rank correlation of exactly -1 is
perfect monotonicity in the direction that quantity runs.

For a *pairwise* metric, `degenerate = True` is a genuine problem and means the metric cannot
distinguish an unrelated field from the reference at all.

### `damage_max`

The largest damage the metric reached anywhere on that axis. A convenient one-number answer to
"how much of its range does this axis exercise?".

### `n_axes`, `n_levels`, `n_frames`

Sample sizes: how many ladder axes contributed to a summary row, how many rungs an axis had,
and how many frames were evaluated. Read the statistics above against these; several of them
are noisy below about twenty frames.

### `n_levels_configured`

How many rungs the config asked for on that axis, against the `n_levels` that were usable. They
differ when a rung resolved to the same experiment as a milder one or to no experiment at all —
see `severity_degenerate`. A gap here is a statement about the field's spectrum, not a mistake:
the acceptance statistics for that axis were computed from fewer points than the config appears
to request, and the run log names which levels were dropped.

### `is_probe`

True for entries that are not monotone axes — the Gaussian field and the unrelated-field
anchor. Excluded from every rank correlation.

### `worst_axis`

The axis on which this metric's `rho` was lowest. Names the weakest point rather than averaging
it away.

### `rho_median`, `rho_min`, `rho_pooled_min`, `monotone_fraction_min`, `sensitivity_level_median`, `saturation_level_median`

The per-axis quantities rolled up to one row per metric and field. `_min` takes the worst axis,
which is the honest summary; `_median` takes the typical one. `rho_min` is the number to read
first, alongside `worst_axis`, which says where it came from.

### `degradation`, `degradation_op`, `degradation_family`

The ladder-entry label, the operator behind it, and the coarse grouping. The **label** is the
unit of rank correlation, so `translate_x` and `translate_y` are two independent axes that
share one operator and one family. The family is used only for colour and grouping.

### `level`, `severity`, `severity_name`, `variant_label`

`level` is the ordinal rung, 0 being the reference; `severity` is the physical knob value
**actually applied** and `severity_name` says what it means (sigma, cutoff, distance);
`variant_label` is the stable identifier used in filenames.

### `higher_is_better`

**What it is.** The metric's declared direction: `True` when a larger value means a *better*
match, `False` for an error measure where larger is worse. Copied onto every row from the metric's
registration, and repeated in the per-axis table so a reader can see which convention a row was
read under.

**Why we report it.** Three of the ordering statistics are one-sided — monotonicity asks whether
the value *rises*, the separability AUC is taken with `alternative="greater"`, and the sensitivity
and saturation levels look for the first median to *exceed* a target. Applied blind they assume
every metric is an error measure, so a metric where larger is better arrives flagged on three
criteria at once while behaving perfectly. Measured on an axis falling cleanly from 1.0 to 0.2:
`rho` −1.0, `monotone_fraction` 0.0, `separability_auc_min` 0.0. Every one of those trips a
configured threshold. The analysis now multiplies the value by the declared direction before
computing those four, so **`rho` = +1 always means "responds correctly to damage"** whichever
convention the metric uses.

**Caveats.** The declaration is trusted, not verified — a metric that declares the wrong direction
will have all four statistics inverted, and the symptom is a clean −1 correlation on every axis.
When a run does not record the column (an older result folder), the direction is instead measured
from the anchor, which is as bad as a field can look by construction: an anchor below the clean
value means larger is better. That inference is unavailable when the anchor is degenerate, and the
direction then defaults to "larger is worse".

**Where it appears.** A column in `results.csv` and in the per-axis table.

### `severity_nominal`, `calibration`

Some severities are written in the config as a *relative* quantity and converted to an absolute
one per field before use. `calibration` names what the config number is relative to and is empty
for an operator that takes absolute units:

| `calibration` | the config severity means | resolved to |
|---|---|---|
| *(empty)* | an absolute value — a coarsening factor, a displacement in cells, noise as a fraction of the fluctuation RMS | used as written |
| `scale` | a fraction of the field's characteristic scale | a smoothing width in cells |
| `energy_above` | the fraction of fluctuation energy to remove from *above* the cutoff (a low-pass) | a cutoff wavenumber |
| `energy_below` | the fraction to remove from *below* the cutoff (a high-pass) | a cutoff wavenumber |

`severity_nominal` is the number as written in the config and `severity` is what was applied, so
a calibrated row carries both. They are equal on an uncalibrated axis.

**Why this exists.** A severity in absolute units lands in a completely different place depending
on where a field keeps its energy, and on this data those places differ by a factor of five: the
density fluctuation varies on about 160 cells against 34 for vorticity. One fixed list of blur
widths was therefore simultaneously far too fine for density — the harshest rung reached 1.2% of
the unrelated-field level, so the axis carried no signal — and about right for vorticity, while
one fixed list of filter cutoffs saturated by the second rung on density, making two of four
rungs the same experiment. Expressing them relatively and resolving against a measurement makes
the same config number mean the same thing on every field.

The calibration itself is measured once per (field, analysis grid) from frames sampled evenly
across the selection, and then held fixed. Re-measuring per frame would make the ladder drift as
the flow evolves, so two frames would no longer be running the same experiment and the per-frame
rank correlation — the primary acceptance statistic — would be comparing different ladders. It is
recorded in `data/calibration.csv`.

### `energy_removed`, `energy_changed`

**What they are.** What a rung *measurably did* to the field, as opposed to what its severity
asked for. `energy_removed` is the fraction of the reference's fluctuation energy the operator
eliminated; `energy_changed` is the fraction of it sitting in the difference between the degraded
field and the reference.

**How they are computed.** Both about the spatial mean, since on a field like density the mean is
four orders of magnitude larger than the fluctuation and energies about zero would say nothing
happened:

- `energy_removed` = 1 − var(degraded) / var(reference)
- `energy_changed` = ⟨(degraded − reference)²⟩ / var(reference)

Recorded per frame; the report shows the median over frames.

**Range and what to expect.** Both are dimensionless fractions. `energy_changed` is non-negative
and unbounded above — an operator can put more energy in the difference than the reference
contains. `energy_removed` runs from 0 to 1 for anything that only takes energy away, and is
**informatively wrong-looking for operators that do something else**: near zero for a translation,
which relocates energy rather than removing it, and negative for additive noise, which adds
energy. Those are not defects; they are the distinction between an operator that destroys structure
and one that displaces or contaminates it.

**Why we report them.** Because a severity is a request and these are the outcome, and on a field
whose energy is concentrated in a few modes the two come apart. A cutoff has to land on an
available set of modes, so the realised removal jumps rather than tracking the request: 69% of
density's fluctuation energy is in the four diagonal modes at |k| = √2 and only 3×10⁻⁵ of it in
the axis modes just below them, so two consecutive available cutoffs there differ by most of the
field. Measured, the mildest sharp high-pass rung on density asks to remove 45% and removes
3×10⁻⁵, and one density low-pass rung asks for 45% and removes 99.997%. Only these columns reveal
that. They are also the honest way to compare a rung across fields, since the same width or cutoff
does very different amounts of damage on a smooth field than on a broadband one.

**Caveats.** `energy_removed` is only a statement about *how much* energy went, never about
*which* energy — a low-pass and a high-pass removing the same fraction are entirely different
experiments. For a nonlinear operator such as a median filter, energy is not partitioned cleanly
between what is kept and what is removed, so read the number as descriptive rather than as an
exact decomposition.

**Where they appear.** Columns in `results.csv`; both in the resolved-severity table in the
reproducibility section, and `energy_removed` annotated on the `energy_spectrum` figure.

### `severity_degenerate`

True when a rung is **not a distinct experiment**: either it resolved to the same severity as a
milder rung on the same axis, or it resolved to a severity at which the operator does nothing at
all. Such rows are excluded from every acceptance statistic.

This happens because a calibrated severity is a real number while many operators act on a
quantised one — a sharp filter selects whole sets of modes, and a windowed kernel takes an odd
number of cells. It is detected by measurement rather than by declaration: two rungs performing
the same operation produce a bitwise identical field and therefore an exactly equal
`energy_changed`.

It is a limit of the field rather than a misconfiguration. 69% of density's fluctuation energy sits
in the four diagonal modes at |k| = √2 and only 3×10⁻⁵ of it below them, so the available cutoffs
there are few and far apart and a sharp filter supports only a couple of distinct rungs however the
config is written. Asking a high-pass for less removal than the lowest available cutoff provides
resolves to a filter that passes essentially every mode.

A related case that is **not** flagged, because the rung is a genuine experiment: a cutoff can be
distinct from its neighbours and still be far from the fraction that was requested, since it must
land on an available set of modes. The resolved-severity table reports the requested and realised
fractions side by side and names any rung where they differ substantially — measured here, one
density low-pass rung asked to remove 45% removes 99.997%, because the nearest available cutoff
below it excludes the diagonal modes that hold most of the field.

Left uncounted, both cases corrupt the statistics rather than merely padding them. A repeated
rung makes the rank correlation score a tie as agreement and makes the adjacent-rung separability
compare a distribution against itself; a rung that does nothing contributes an exactly-zero
damage, which made one axis appear to span eleven orders of magnitude.

Compare `n_levels` against `n_levels_configured` to see how many rungs an axis actually
contributed.

### `analysis_grid`, `remap_op`

The resolution the measurement was made on, and the operator that got it there. Recorded on
every row so a number is never separated from the grid it was computed on.

### `dataset`, `dataset_family`, `complexity_rank`, `param_reynolds`, `param_mach`, `param_resolution`, `trajectory`

Which dataset, and where it sits in an ordered family of increasing physical complexity.
Present on every row as the groundwork for comparing metrics across datasets; not yet consumed.

### `frame_index`, `time`

The index into the source trajectory, and the corresponding physical time.

### `metric`, `tracker_id`, `arity`, `field`, `component`

Which metric, its identifier from the metrics document, whether it compares two fields or
characterises one, which physical field, and — for a metric returning a vector — which element.

### `seed`, `wall_time_s`

The run seed, and the time the metric call itself took.

### `flags`

**Advisory only.** A semicolon-separated list of the configured reference values a row did not
meet, for example `spearman=0.40 < 0.9; separability_auc=0.31 < 0.8`. An empty entry means
nothing was flagged — **not** that the metric is approved. Thresholds live in one config block
and re-flagging needs no recomputation, so changing your mind is a config edit.

---

## The degradation axes

Twenty operators in seven families. `uv run python -m degradations` lists them with their
severity units. Which failure modes you probe determines what the measurements mean, so this
list is as important as the metric list.

**Smoothing** — the loss of small-scale structure, the failure most expected of an
over-regularised surrogate.

| operator | severity | what it does, and why it is separate |
|---|---|---|
Every width here is configured as a **fraction of the field's characteristic scale** and resolved
to cells per field (`calibration: scale`).

| operator | severity | what it does, and why it is separate |
|---|---|---|
| `gaussian_blur` | fraction of scale → sigma | Attenuates every scale and amplifies none, so it is the well-behaved reference the others are read against. Takes a fractional sigma, so its rungs stay distinct at any spacing |
| `box_blur` | fraction of scale → width | A square moving average. Its transfer function is a sinc, so it *amplifies* some wavenumbers, and it is anisotropic. Rounded to an **odd** width |
| `median_blur` | fraction of scale → width | Nonlinear, and preserves the sharp edges a Gaussian smears. A metric that scores this the same as Gaussian blur at matched width is not seeing sharp structure. Rounded to an **odd** width |
| `disk_blur` | fraction of scale → radius | Isotropic top-hat, unlike the square box |
| `epanechnikov_blur` | fraction of scale → radius | The mean-square-optimal smoothing kernel |

**The windowed kernels round to an odd number of cells on purpose.** An even window has no centre
cell, so it is placed asymmetrically and displaces the field by half a cell. Since the whole
concern of this project is that metrics over-punish displacement, that artefact dominates:
measured on vorticity, widths that rounded to 2, 3, 6 and 13 cells gave damage 0.0121, 0.0041,
0.0338 and 0.0880 — non-monotone, because the even rung carried a half-cell shift the odd one did
not. It also means two scale fractions closer than about `2 / scale` land on the same width and
one of them is flagged `severity_degenerate`.

**Spectral** — damage confined to chosen scales.

| operator | severity | notes |
|---|---|---|
Every cutoff here is configured as the **fraction of fluctuation energy the filter removes** and
resolved to a wavenumber per field. Both directions therefore mean the same thing and both rise
with damage, which they did not when the severity was an absolute cutoff.

| operator | severity | notes |
|---|---|---|
| `lowpass_ideal` | fraction of energy removed | Sharp cutoff, removing the small scales; rings near sharp features |
| `lowpass_butterworth` | fraction of energy removed | Smooth rolloff; the ringing-free control for the above, and it resolves rungs a sharp filter cannot |
| `highpass_ideal` | fraction of energy removed | Removes large scales. **Keeps the spatial mean deliberately** — deleting it removes a component four orders of magnitude larger than anything the cutoff controls, and before this was fixed every rung gave an identical damage of 2.7e7 and the axis carried no ordering at all |
| `highpass_butterworth` | fraction of energy removed | As above, smooth |

**The high-pass axis has a narrow usable window on these fields, and that is a property of the
data.** Both filters are floored at the lowest usable cutoff, |k| = 1, and on density the modes
at that magnitude hold almost nothing while the diagonal modes just above them hold 69% of the
fluctuation energy. A mild request therefore resolves to a filter that passes essentially every
mode; one step harsher puts the damage already most of the way to an unrelated field.
The configured window is the widest measured — it spans a factor 3.4 in damage on vorticity and
gives density two usable rungs of four — so the high-pass axis alone does not reach the factor of
five that the other axes do. No severity list fixes this; a field with more energy at high
wavenumbers would.
| `band_attenuate` | retained fraction | Damages one wavenumber band only. The direct test of whether a metric is scale-selective |

**Geometric** — the double-penalty probe. Shape and amplitude stay exactly correct; only
position changes.

| operator | severity | notes |
|---|---|---|
| `translate` | distance, cells | Whole-cell periodic shift. Quantised: the smallest step is one cell |
| `translate_subpixel` | distance, cells | Fractional shift by a Fourier phase ramp, exact on a periodic grid. Resolves the sub-cell region where metrics differ most, and reproduces `translate` at integer distances |
| `random_large_translation` | draw index | Not a rung. Measures the unrelated-field anchor |

**Resolution.**

| operator | severity | notes |
|---|---|---|
| `coarsen` | factor | Conservative block average, then back to the fine grid |
| `subsample` | factor | Point-sampling instead, as the non-conservative control. At factor 8 this retains 102% of the variance where averaging retains 73%, because it folds small scales back in rather than removing them |

**Stochastic.**

| operator | severity | notes |
|---|---|---|
| `additive_noise` | fraction of fluctuation RMS | **Relative to the fluctuation, never the raw RMS.** Density here is 1.0 +/- 1.8e-4, so a fraction of the raw RMS would make even the mildest rung total destruction |
| `multiplicative_noise` | relative | Error proportional to the local value |
| `gaussian_impostor` | — | Not a rung. See Group B |

**Pointwise** — the complement of displacement: correct position, wrong magnitude.

| operator | severity | notes |
|---|---|---|
| `gain` | relative | Scales the fluctuation, leaving the mean and every gradient's sign intact |
| `bias` | fraction of fluctuation RMS | A uniform offset, invisible to any metric built on fluctuations or gradients |
| `identity` | — | Rung 0 |

---

## The figures

| figure | section | what it shows, and how to read it |
|---|---|---|
| `energy_spectrum` | 3 | Cumulative fluctuation energy against wavenumber, per field, with the applied spectral cutoffs drawn on. This sets the resolution of every filter ladder: a spectral severity is a fraction of energy to remove and is converted to a cutoff using exactly this curve, so where the curve rises sharply neighbouring rungs land on the same set of modes and become the same experiment. The density curve is almost a step — 3×10⁻⁵ of its fluctuation energy at or below |k| = 1 and 69% at |k| = √2 — which is why a sharp filter has only a couple of usable rungs there; vorticity rises gradually, 50% by |k| = 3.2 and 99% by 51, and its cutoffs spread over more than a factor of ten. Dashed lines are cutoffs in use, dotted lines rungs excluded for repeating a milder rung or for doing nothing. It says nothing about phase — two fields with identical curves can look entirely different, which is the premise of the impostor test |
| `ladder_curves` | 3 | Value against rung for every axis, with an interquartile band over frames. The curve the correlation summarises. Flat means blind to that failure mode |
| `monotonicity_heatmap` | 4 | `rho` for every metric against every axis. Down a column: is this metric monotone? Across a row: what does it detect? Hatched cells fall below the reference value |
| `rung_separation` | 5 | The spread of each rung across frames, as violins. Where neighbouring violins overlap, the metric cannot rank models one rung apart |
| `field_gallery` | 6 | The per-cell contribution to the metric, on **shared colour limits**. Autoscaling each panel would make a heavily smoothed field look identical to the reference. A displaced feature shows as two lobes — one where it should be and is not, one where it is and should not be |
| `selectivity_profile` | 7 | Each metric's response across every axis, as grouped bars. Needs two or more metrics |
| `deception_panel` | 8 | Damage assigned to the Gaussian field (star) against the ordinary rungs (open circles). A star near zero means the metric sees only second-order statistics |
| `displacement_response` | 9 | Damage against displacement distance, log x. Shape and amplitude are exactly correct at every point on this curve; only position changes. The project's central figure |
| `cost_frontier` | 10 | Worst-axis correlation against cost. Upper left is useful; upper right is right-but-unaffordable, so a diagnostic rather than a loss |

Every figure has a CSV of exactly the numbers plotted, in `data/figure_data/`. No number
appears in the report without a machine-readable source in the same folder.

---

## Glossary

**Double penalty.** A sharp feature that is correct in shape and amplitude but slightly
displaced is penalised twice by a pointwise norm — once for being absent where it should be,
once for being present where it should not. Named in weather verification; the same pathology
is called cycle skipping in seismic inversion.

**Phase-blind.** Sensitive only to Fourier amplitudes, and therefore unable to distinguish a
structured field from a Gaussian one with the same spectrum.

**Intermittency.** The tendency of turbulent quantities to have heavy-tailed distributions —
rare, intense events. Measured here by flatness, which is 3 for a Gaussian field and about 17
for our vorticity. It is the first property an over-smoothed surrogate destroys and the last
one a pointwise norm notices.

**Flatness.** The fourth moment normalised by the square of the second,
mean(x^4) / mean(x^2)^2. Exactly 3 for a Gaussian.

**Reference, or clean.** Rung 0: the undamaged field.

**Unrelated field.** A field with identical statistics and no positional alignment. Defines
D = 1.

**Primitive and derived fields.** Density and velocity are stored and are remapped directly.
Vorticity and pressure are computed from them, and are recomputed after any remap rather than
averaged.
