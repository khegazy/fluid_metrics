# What the suite measures

> This file explains **every quantity the evaluation reports** and the protocol behind
> those quantities. What each individual metric measures, and what each metric did on a
> recorded run, lives on that metric's own page — see
> [metrics/mse/card.md](metrics/mse/card.md) for the worked example, or
> `docs/catalog.json` for all of them at once. This file is served as one page of the
> documentation site, and a copy is placed in every results folder.

A reference for every quantity the evaluation reports, written for someone who has not
read the code. Open this page when a table column says `separability_auc_min = 0.62` and
you need to know what that means and whether to care.

A copy of this file sits in every results folder, so that a folder still explains its own
numbers after being sent to someone else.

## How the measurement works

We have one trusted simulation and no model predictions to test against, so what we
compare against is manufactured. The reference field is damaged in controlled steps, and
each candidate metric is asked to score the damaged versions against the original.

Four terms are used everywhere below.

**Degradation.** One way of damaging a field, together with the single knob that controls
how hard it is applied — for instance Gaussian blur, applied at sigma = 0.5, 1, 2, 4 and 8
cells. A degradation is *the unit of rank correlation*: the whole point is to check that a
metric puts one degradation's own strengths in the right order. Blur at sigma = 2 and a
4-cell translation have no order relative to one another, and neither do Gaussian blur and
median blur even though both smooth, so a correlation is never computed across two
different degradations.

In the CSV column names and in some figures a degradation is called an **axis**, and you
will see that word in identifiers such as `n_axes`, `worst_axis` and
`axis_detail__field-*.csv`. The two words mean the same thing. The prose uses
"degradation", because "axis" beside a column named `field` reads as a direction in space.

**Severity level.** One damaged copy of the reference: one degradation applied at one
strength. Severity level 0 is the reference itself, undamaged, so any metric that compares
two fields must return exactly zero there.

**Severity direction.** Some knobs make things worse as the number grows (a blur width) and
some as the number shrinks (a low-pass cutoff). Each operator declares which way its knob
runs, and the severity levels are then sorted into increasing-damage order before they are
numbered. A cutoff list written `[64, 32, 16, 8]` therefore gets sensible level numbers
instead of a perfectly inverted sequence.

**Damage, written D.** A raw mean squared error and a raw transport distance are not
comparable numbers, so every value is also reported on one shared scale that carries no
units:

    D = (value - clean) / (unrelated - clean)

`clean` is the value the metric gives the undamaged reference, and `unrelated` is the
value it gives a field with the same statistics and no relationship to the truth. That
second number is *measured*, never assumed. D = 0 is a perfect match and D = 1 is what a
metric gives two fields that share every statistic but have no positional alignment.
Dividing by the clean value instead would not work, because mean squared error is exactly
zero there.

**The analysis grid.** Both fields are placed on one common grid before anything is
measured, by averaging over blocks of cells. Fields that are computed from other fields —
vorticity, which is the curl of velocity — are **recomputed** on that grid rather than
averaged directly, because the average of a curl is not the curl of the average. Measured,
the difference between recomputing and averaging is 5.6% / 18.3% / 25.9% at coarsening
factors 2 / 4 / 8, which is not a rounding detail.

**Why so many numbers per degradation.** A metric can put the strengths in the right order
and still be useless: if neighbouring severity levels overlap from one snapshot to the next,
the metric cannot rank two models that differ by one step. A metric can also be correctly
ordered and still uninformative: if the metric runs out of range at severity level 1, it has
no resolution left in the regime that matters. Each quantity below closes one of those gaps.

## Group A: does the metric respond correctly?

### `rho` — did the metric order the strengths correctly?

**What it is.** How reliably the metric orders the severity levels of one degradation from mildest to worst.
1.0 means it gets the order right every time, 0 means no relationship, -1 means it is exactly
backwards.

**How it is computed.** Spearman rank correlation between the severity level number and the metric
value, computed **within each frame separately**, then the median over frames is reported.

**Why not pooled over frames.** Because that measures the wrong thing. The flow evolves along
the trajectory, and on this data the density perturbation grows six orders of magnitude from
start to end. Pooling every frame together means the worst severity level early is numerically smaller
than the mildest severity level late, so the correlation collapses even when the ordering is perfect
inside every single frame. Measured: every density degradation was perfectly ordered within every
frame while the pooled value read between 0.10 and 0.91 depending on the degradation. Per-frame is
the statistic that answers the question actually being asked.

**Range.** -1 to 1, dimensionless.

**Good and bad.** 1.0 is what a well-behaved metric gives on a well-behaved degradation; most of our
baselines achieve it on most degradations. Below about 0.9, look at `rho_frame_min` and at the degradation
itself before blaming the metric — a common cause is a degradation with no dynamic range rather
than a defective metric.

**Why we report it.** This is the core requirement: a metric used for model selection must
not rank a worse model as better. A non-monotone metric is worse than no metric, because
optimising against it moves in the wrong direction.

**Caveats.** With only four or five severity levels the per-frame value takes a small discrete set of
values, so the median over frames is coarse. It says nothing about *how much* the metric
changes — see `sensitivity_level` and the damage columns for that.

**Where it appears.** `axis_detail__field-*.csv`; the heatmap figure; `rho_min` in the
summary.

### `rho_frame_min` — the worst single snapshot behind `rho`

**What it is.** The worst per-frame value behind `rho`. If `rho` is 1.0 but this is -0.8, the
metric orders the severity levels correctly on most frames and gets them badly wrong on at least one.

**Why we report it.** A median hides a tail. On our data MAE on vorticity had `rho = 0.40`
with `rho_frame_min = -0.8` on the high-pass degradation, and that tail is what identified the
problem as an unusable degradation rather than a marginal one.

**Where it appears.** `axis_detail__field-*.csv`.

### `rho_pooled` — the same correlation computed the wrong way, kept for comparison

**What it is.** The rank correlation computed by pooling every frame together, which is the
statistic we deliberately do *not* use as primary. Kept for comparison only.

**How to read it.** A large gap between `rho` and `rho_pooled` indicates a **non-stationary
field** — one whose overall amplitude is changing along the trajectory — not a defective
metric. If they agree, the field is roughly stationary over the frames sampled.

**Where it appears.** `axis_detail__field-*.csv`; `rho_pooled_min` in the summary.

### `rho_ci_lo`, `rho_ci_hi` — how much `rho` would move on a different sample of snapshots

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

### `monotone_fraction` — how often the ordering was perfect, with no ties

**What it is.** The fraction of frames on which the severity levels are ordered *strictly* correctly,
with no ties or inversions anywhere in the sequence.

**Range.** 0 to 1. 1.0 means every frame was perfect.

**Good and bad.** This is stricter than `rho`, which tolerates a single swap. Read the two
together: high `rho` with a low `monotone_fraction` means the metric usually gets the overall
trend right but often muddles a neighbouring pair.

**Where it appears.** `axis_detail__field-*.csv`; `monotone_fraction_min` in the summary.

### `separability_auc_min` — can the metric tell neighbouring strengths apart?

**What it is.** Whether the metric can actually tell two *neighbouring* severity levels apart, given how
much its value scatters from frame to frame. The smallest such separation across all adjacent
pairs on the degradation.

**How it is computed.** For each adjacent pair of severity levels, the Mann-Whitney U statistic divided
by the product of the sample sizes — the probability that a randomly chosen frame from the
worse severity level scores worse than a randomly chosen frame from the milder severity level. The minimum over
pairs is reported.

**Range.** 0 to 1. 0.5 means the two severity_levels' distributions are indistinguishable; 1.0 means
they never overlap.

**Good and bad.** Above 0.8 the metric can rank models one severity level apart with confidence. Around
0.5 it cannot, no matter how clean the median curve looks — which is exactly the failure a
monotonicity number alone would hide.

**Why we report it.** Monotone medians are not enough. If you intend to select between two
models that differ by roughly one severity level's worth of quality, this number tells you whether the
metric can see the difference at all.

**Caveats.** **Deliberately reported without a p-value.** The metric trace is autocorrelated
in time, so any significance test assuming independent samples would report far more
confidence than the data supports. Treat this number purely as a description of how much
two distributions overlap. It also needs a reasonable number of snapshots; with ten or
twenty it is noisy.

**Where it appears.** `axis_detail__field-*.csv`; `separability_auc_min` in the summary.

### `sensitivity_level` — how early does the metric start complaining?

**What it is.** The first severity level at which the metric has moved 10% of the way from its clean
value to the unrelated-field value. In short: how early does it start complaining?

**How it is computed.** The lowest severity level whose median value reaches `clean + 0.10 * span`,
where `span` is the **shared** clean-to-unrelated range rather than the degradation's own maximum.
Using each degradation's own range would make a degradation that barely damages the field look just as
sensitive as one that destroys it, so the numbers would not be comparable between rows.

The 10% fraction is fixed once in the code and is never tuned per metric — otherwise the
quantity becomes something one can adjust until the answer is pleasing.

**Range.** An integer severity level number, or `--` when the threshold is never reached.

**Good and bad.** Lower is more sensitive, but earlier is not automatically better: a metric
that fires at severity level 1 on every degradation may simply be noisy. Read it against the `field_gallery`
figure, which shows what each severity level actually looks like — a metric that first complains only
after the field is visibly ruined is not earning its place.

**Where it appears.** `axis_detail__field-*.csv`; `sensitivity_level_median` in the summary.

### `saturation_level` — when does the metric run out of range?

**What it is.** The first severity level at which the metric has used up 90% of its range — beyond which
it can no longer distinguish worse from much worse.

**Range.** An integer severity level, or `--` if never reached, which is the common case and is
informative in itself: it means that no degradation applied here is as damaging as losing the correlation entirely.

**Good and bad.** Saturating at severity level 1 is the quantitative form of the double-penalty
complaint: the metric reports "as bad as possible" for damage that is in fact mild, so it
cannot rank anything above that point.

**Where it appears.** `axis_detail__field-*.csv`; `saturation_level_median` in the summary.

---

## Group B: can the metric be fooled?

Two fields are constructed specifically to mislead a metric. These are the **trap tests**.
Each targets a different weakness, and neither is a strength on any degradation, so both
are excluded from every rank correlation.

### `gaussian_impostor_value`, `gaussian_impostor_damage` — the fake prediction with the right spectrum

**What it is.** The metric's response to a field that has the reference's energy spectrum
*exactly* and none of its structure — a fake prediction that is right about how much
energy sits at each scale and wrong about where anything is.

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

**What this test actually catches.** Not the ordinary error norms. Measured, mean squared
error gives this field 0.51-0.80 depending on which physical field is used, so mean squared
error rejects the fake prediction firmly — scrambling the phases leaves a field that is
uncorrelated with the reference cell by cell, which is exactly what an error norm looks at.
The trap is aimed instead at metrics whose entire content is the amplitude spectrum: a
metric comparing energy spectra, or one comparing two-point correlations, scores this fake
prediction as **perfect**. Until such metrics are implemented this column will look
uninformative, and a report in which every metric passes it should not be read as
reassuring.

**Caveats.** Values above 1 are possible and have been observed (MAE on vorticity, 1.38),
meaning the metric judges the Gaussian field worse than a genuinely unrelated turbulent field.
A plausible mechanism is that real vorticity is intermittent, so two independent turbulent
fields share large quiet regions where the difference is small, while a Gaussian field of
matched variance has none — but this is conjecture and has not been tested.

**Where they appear.** `deception_table.csv`; the deception figure; the summary.

### `gaussian_impostor_nearest_level` — the real damage the fake prediction is equivalent to

**What it is.** The ordinary severity level whose damage is closest to the Gaussian field's, which is
what makes the damage figure interpretable. An entry of `translate_x=16` reads: *this metric
considers the Gaussian field about as bad as displacing the reference by 16 cells.*

**Where it appears.** `deception_table.csv`.

### `uncorrelated_value`, `uncorrelated_damage` — the unrelated field that anchors the damage scale

**What it is.** The value the metric gives two fields with identical statistics and no
positional alignment. This is the anchor that defines D = 1, so `uncorrelated_damage` reads
exactly 1.000 by construction and serves as a consistency check rather than a result.

**How it is measured.** The reference is translated by a large random offset, drawn from the
middle half of each spatial axis of the domain. On a periodic domain a translation preserves every single- and
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

## Group C: is the metric worth a place on the panel?

### `cost_s`, `median`, `p95` — how long one evaluation takes

**What it is.** Wall-clock seconds for a single metric evaluation on one field and one variant.
Times the metric call only — reading the data and building the degraded variants are excluded,
so this is the metric's own cost.

**Good and bad.** Nothing here is absolute; the useful comparison is against other metrics and
against the projection below.

**Where they appear.** `cost_table.csv`; `cost_s` in the summary.

### `per_frame_s`, `full_trajectory_s` — that cost scaled up to a whole trajectory

**What it is.** The cost scaled up: `per_frame_s` is one evaluation times the number of
damaged copies the run produced, and `full_trajectory_s` projects that to all 10001 frames.

**Why we report it.** This is the number that decides usability. A metric that takes a second
per evaluation is fine as an occasional diagnostic and impossible inside a training loop, and
the raw per-call figure does not make that obvious.

**Caveats.** A linear projection, so it ignores any caching or vectorisation a real
implementation might exploit, and it assumes the present number of damaged copies.

**Where they appear.** `cost_table.csv`.

### `cost_relative`, `relative` — that cost against the cheapest metric in the run

**What it is.** Cost divided by the cheapest metric in the same run, so 2.0 means twice the
cost of the cheapest thing measured.

**Caveats.** The baseline is whatever happened to be cheapest in *this* run, so the number is
not comparable between runs with different metric sets.

**Where they appear.** `cost_table.csv`; `cost_relative` in the summary.

### The redundancy matrix — which metrics are duplicates of each other

**What it is.** Rank correlation between every pair of metrics, over every degradation. Two
metrics that correlate near 1 are near-duplicates and one of them is a wasted panel slot.

**How it is computed.** One observation per (degradation, severity level), using the median over frames — which
is the level at which the panel decision is actually made. The **reference severity level is excluded**:
every pairwise error metric is exactly zero there, so keeping it would add a point all metrics
share by construction and pull every correlation toward +1.

**Range.** -1 to 1. The configured reference for "redundant" is 0.95.

**Caveats, and an important one.** High rank correlation means the metrics *order* the
degradations the same way. It does **not** mean they weight them the same. Measured on our
data, MAE and MSE correlate at 0.995 over every degradation, yet MAE assigns 55 times the damage
MSE does at an eighth of a cell of displacement, because one is linear and the other quadratic
in the displacement. For selecting between models by ranking they are duplicates; as training
losses they are not. Read this matrix alongside the displacement figure, never alone.

**Where it appears.** `redundancy_table.csv`, in the comparison folder only, since it needs at
least two metrics.

### The selectivity profile — what one metric detects, across everything

**What it is.** One metric's `rho` across every degradation, read as a row rather than a column: a
fingerprint of *what that metric detects*.

**How to read it.** Two metrics with near-identical profiles are redundant even when their
magnitudes differ. A profile that is uniform across every degradation indicates a metric responding to
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

The metric's value on the reference severity level, the median over frames. Exactly 0 for any pairwise
error metric — a nonzero entry means a bug.

### `value_min`, `value_max`

The smallest and largest values the metric took on that degradation, for a quick sense of
its working range before any normalisation.

### `value_uncorrelated`, `span`

`value_uncorrelated` is the measured unrelated-field anchor, and `span` is
`value_uncorrelated - value_clean`: the metric's full working range, and the denominator of the
damage score.

### `anchor_source`

Where the unrelated-field anchor came from. `uncorrelated` means it was measured properly.
Anything ending in `@max` means the run had no anchor entry and the largest configured
translation was used instead, which **understates** it — a 16-cell displacement reaches
only about 0.6 of the true value on this data, so damage scores would be inflated by
roughly 1.6x. If you see `@max`, add the `uncorrelated` entry to the configured
degradations and re-run.

### `degenerate` — the metric has no range to work with on this field

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
metric between two fields. Enstrophy is instead a rough alarm on a single field, which is
exactly how it is intended to be used. `rho = -1` is also correct rather than alarming:
smoothing destroys small-scale structure, so enstrophy *falls* monotonically as damage
increases, and a rank correlation of exactly -1 is perfect monotonicity in the direction
that quantity runs.

For a *pairwise* metric, `degenerate = True` is a genuine problem and means the metric cannot
distinguish an unrelated field from the reference at all.

### `damage_max`

The largest damage the metric reached anywhere on that degradation. A convenient
one-number answer to "how much of its range does this degradation exercise?".

### `n_axes`, `n_levels`, `n_frames`

Sample sizes: how many degradations contributed to a summary row, how many severity levels
a degradation had, and how many frames were evaluated. Read the statistics above against
these; several of them are noisy below about twenty frames.

### `n_levels_configured`

How many severity levels the config asked for on that degradation, against the `n_levels`
that were usable. They differ when a severity level resolved to the same experiment as a
milder one or to no experiment at all — see `severity_degenerate`. A gap here is a
statement about the field's spectrum, not a mistake: the acceptance statistics for that
degradation were computed from fewer points than the config appears to request, and the
run log names which levels were dropped.

### `is_probe` — this row is a trap test, not an ordered degradation

True for entries that are not monotone degradations — the Gaussian field and the
unrelated-field anchor. Excluded from every rank correlation.

### `worst_axis` — the degradation this metric handled worst

The degradation on which this metric's `rho` was lowest. Names the weakest point rather
than averaging it away.

### `rho_median`, `rho_min`, `rho_pooled_min`, `monotone_fraction_min`, `sensitivity_level_median`, `saturation_level_median`

The per-degradation quantities rolled up to one row per metric and field. `_min` takes the
worst degradation, which is the honest summary; `_median` takes the typical one. `rho_min`
is the number to read first, alongside `worst_axis`, which says where it came from.

### `degradation`, `degradation_op`, `degradation_family`

The label of the configuration entry, the operator behind that entry, and the coarse
grouping. The **label** is the unit of rank correlation, so `translate_x` and
`translate_y` are two independent degradations that share one operator and one family. The
family is used only for colour and grouping.

### `level`, `severity`, `severity_name`, `variant_label`

`level` is the severity level as a whole number counting up from 0, which is the
reference; `severity` is the physical knob value **actually applied** and `severity_name`
says what it means (sigma, cutoff, distance); `variant_label` is the stable identifier
used in filenames.

### `higher_is_better` — which direction counts as a better match

**What it is.** The metric's declared direction: `True` when a larger value means a *better*
match, `False` for an error measure where larger is worse. Copied onto every row from the metric's
registration, and repeated in the per-degradation table so a reader can see which convention a row was
read under.

**Why we report it.** Three of the ordering statistics are one-sided — monotonicity asks whether
the value *rises*, the separability AUC is taken with `alternative="greater"`, and the sensitivity
and saturation levels look for the first median to *exceed* a target. Applied blind they assume
every metric is an error measure, so a metric where larger is better arrives flagged on three
criteria at once while behaving perfectly. Measured on a degradation falling cleanly from 1.0 to 0.2:
`rho` −1.0, `monotone_fraction` 0.0, `separability_auc_min` 0.0. Every one of those trips a
configured threshold. The analysis now multiplies the value by the declared direction before
computing those four, so **`rho` = +1 always means "responds correctly to damage"** whichever
convention the metric uses.

**Caveats.** The declaration is trusted, not verified — a metric that declares the wrong direction
will have all four statistics inverted, and the symptom is a clean −1 correlation on every degradation.
When a run does not record the column (an older result folder), the direction is instead measured
from the anchor, which is as bad as a field can look by construction: an anchor below the clean
value means larger is better. That inference is unavailable when the anchor is degenerate, and the
direction then defaults to "larger is worse".

**Where it appears.** A column in `results.csv` and in the per-degradation table.

### `severity_nominal`, `calibration` — strengths written relative to the field's own properties

Some severities are written in the config as a *relative* quantity and converted to an absolute
one per field before use. `calibration` names what the config number is relative to and is empty
for an operator that takes absolute units:

| `calibration` | the config severity means | resolved to |
|---|---|---|
| *(empty)* | an absolute value — a coarsening factor, a displacement in cells, noise as a fraction of the fluctuation RMS | used as written |
| `scale` | a fraction of the field's characteristic scale | a smoothing width in cells |
| `energy_above` | the fraction of fluctuation energy to remove from *above* the cutoff (a low-pass) | a cutoff wavenumber |
| `energy_below` | the fraction to remove from *below* the cutoff (a high-pass) | a cutoff wavenumber |

`severity_nominal` is the number as written in the config and `severity` is what was
applied, so a calibrated row carries both. They are equal on an uncalibrated degradation.

**Why this exists.** A severity in absolute units lands in a completely different place depending
on where a field keeps its energy, and on this data those places differ by a factor of five: the
density fluctuation varies on about 160 cells against 34 for vorticity. One fixed list of blur
widths was therefore simultaneously far too fine for density — the harshest severity level reached 1.2% of
the unrelated-field level, so the degradation carried no signal — and about right for vorticity, while
one fixed list of filter cutoffs saturated by the second severity level on density, making two of four
severity levels the same experiment. Expressing them relatively and resolving against a measurement makes
the same config number mean the same thing on every field.

The calibration itself is measured once per (field, analysis grid) from frames sampled
evenly across the selection, and then held fixed. Re-measuring per frame would make the
strengths drift as the flow evolves, so two frames would no longer be running the same
experiment and the per-frame rank correlation — the primary acceptance statistic — would
be comparing different ladders. It is recorded in `data/calibration.csv`.

### `energy_removed`, `energy_changed` — what the degradation measurably did, not what was asked for

**What they are.** What a severity level *measurably did* to the field, as opposed to what its severity
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
the modes lying on the coordinate axes just below them, so two consecutive available cutoffs there differ by most of the
field. Measured, the mildest sharp high-pass severity level on density asks to remove 45% and removes
3×10⁻⁵, and one density low-pass severity level asks for 45% and removes 99.997%. Only these columns reveal
that. They are also the honest way to compare a severity level across fields, since the same width or cutoff
does very different amounts of damage on a smooth field than on a broadband one.

**Caveats.** `energy_removed` is only a statement about *how much* energy went, never about
*which* energy — a low-pass and a high-pass removing the same fraction are entirely different
experiments. For a nonlinear operator such as a median filter, energy is not partitioned cleanly
between what is kept and what is removed, so read the number as descriptive rather than as an
exact decomposition.

**Where they appear.** Columns in `results.csv`; both in the resolved-severity table in the
reproducibility section, and `energy_removed` annotated on the `energy_spectrum` figure.

### `severity_degenerate` — this strength was not a distinct experiment

True when a severity level is **not a distinct experiment**: either it resolved to the
same severity as a milder severity level on the same degradation, or it resolved to a
severity at which the operator does nothing at all. Such rows are excluded from every
acceptance statistic.

This happens because a calibrated severity is a real number while many operators act on a
quantised one — a sharp filter selects whole sets of modes, and a windowed kernel takes an odd
number of cells. It is detected by measurement rather than by declaration: two severity levels performing
the same operation produce a bitwise identical field and therefore an exactly equal
`energy_changed`.

It is a limit of the field rather than a misconfiguration. 69% of density's fluctuation energy sits
in the four diagonal modes at |k| = √2 and only 3×10⁻⁵ of it below them, so the available cutoffs
there are few and far apart and a sharp filter supports only a couple of distinct severity levels however the
config is written. Asking a high-pass for less removal than the lowest available cutoff provides
resolves to a filter that passes essentially every mode.

A related case that is **not** flagged, because the severity level is a genuine experiment: a cutoff can be
distinct from its neighbours and still be far from the fraction that was requested, since it must
land on an available set of modes. The resolved-severity table reports the requested and realised
fractions side by side and names any severity level where they differ substantially — measured here, one
density low-pass severity level asked to remove 45% removes 99.997%, because the nearest available cutoff
below it excludes the diagonal modes that hold most of the field.

Left uncounted, both cases corrupt the statistics rather than merely padding them. A
repeated severity level makes the rank correlation score a tie as agreement and makes the
adjacent-severity level separability compare a distribution against itself; a severity
level that does nothing contributes an exactly-zero damage, which made one degradation
appear to span eleven orders of magnitude.

Compare `n_levels` against `n_levels_configured` to see how many severity levels a
degradation actually contributed.

### `analysis_grid`, `remap_op`

The resolution the measurement was made on, and the operator that got it there. Recorded on
every row so a number is never separated from the grid it was computed on.

### `dataset`, `dataset_family`, `complexity_rank`, `param_reynolds`, `param_mach`, `param_resolution`, `trajectory`

Which dataset, and where it sits in an ordered family of increasing physical complexity.
Present on every row as the groundwork for comparing metrics across datasets; not yet consumed.

### `frame_index`, `time`

The index into the source trajectory, and the corresponding physical time.

### `metric`, `arity`, `field`, `component`

Which metric, whether it compares two fields or characterises one, which physical field,
and — for a metric returning a vector — which element.

### `seed`, `wall_time_s`

The run seed, and the time the metric call itself took.

### `n_members`, `target_value` — the probabilistic columns

Both are empty on every row a deterministic metric produced, which is most of them.

`n_members` is the ensemble size the metric actually saw. It is recorded because both CRPS
and the spread-to-skill ratio depend on it: the fair CRPS estimator is unbiased at any
ensemble size but noisier at small ones, and the spread carries a finite-ensemble
correction of sqrt((N+1)/N) that is 12% at four members and under 1% at fifty. Two runs of
the same model at different ensemble sizes are comparable only with this column in view.

`target_value` is the value a perfectly calibrated prediction attains, when that value is
not zero. Almost every metric here is an error and leaves this empty; the spread-to-skill
ratio sets it to 1. It is what tells the analysis that a metric is wrong in **two**
directions rather than one — see "Metrics with a target value" below.

### Metrics with a target value

Every ordering statistic in this suite — the rank correlation, the monotone fraction, the
adjacent-severity separability, the sensitivity and saturation levels — assumes that damage
moves a metric one way. The spread-to-skill ratio breaks that assumption honestly: it is
calibrated at 1, reads low when an ensemble is overconfident and high when it hedges, and
both are failures.

The suite adapts rather than the metric. The reported value stays the raw ratio, as the
forecast-verification literature reports it, so a reader who sees 0.4 knows immediately
that the ensemble is too narrow. The **ordering** statistics are computed on the distance
from the target, |log(value / target)|, which is zero when calibrated and rises in either
direction. The log makes the scale symmetric, since half the calibrated spread and twice it
are equally wrong. A value of zero — an ensemble collapsed onto its mean, claiming
certainty it has not earned — is the furthest point from calibration there is, and is
ranked as such rather than dropped.

Without this the axis would arrive flagged on three criteria at once, and the flags would
be describing the analysis rather than the metric.

### `flags` — advisory notes, never a verdict

**Advisory only.** A semicolon-separated list of the configured reference values a row did not
meet, for example `spearman=0.40 < 0.9; separability_auc=0.31 < 0.8`. An empty entry means
nothing was flagged — **not** that the metric is approved. Thresholds live in one config block
and re-flagging needs no recomputation, so changing your mind is a config edit.

---

## The degradations

Twenty-three operators in eight families. `python -m degradations` lists them with their
severity units. Which failure modes you test for determines what the measurements mean, so
this list is as important as the list of metrics.

**Smoothing** — the loss of small-scale structure, the failure most expected of an
over-regularised surrogate.

| operator | severity | what it does, and why it is separate |
|---|---|---|
Every width here is configured as a **fraction of the field's characteristic scale** and resolved
to cells per field (`calibration: scale`).

| operator | severity | what it does, and why it is separate |
|---|---|---|
| `gaussian_blur` | fraction of scale → sigma | Attenuates every scale and amplifies none, so it is the well-behaved reference the others are read against. Takes a fractional sigma, so its severity levels stay distinct at any spacing |
| `box_blur` | fraction of scale → width | A square moving average. Its transfer function is a sinc, so it *amplifies* some wavenumbers, and it is anisotropic. Rounded to an **odd** width |
| `median_blur` | fraction of scale → width | Nonlinear, and preserves the sharp edges a Gaussian smears. A metric that scores this the same as Gaussian blur at matched width is not seeing sharp structure. Rounded to an **odd** width |
| `disk_blur` | fraction of scale → radius | Isotropic top-hat, unlike the square box |
| `epanechnikov_blur` | fraction of scale → radius | The mean-square-optimal smoothing kernel |

**The windowed kernels round to an odd number of cells on purpose.** An even window has no centre
cell, so it is placed asymmetrically and displaces the field by half a cell. Since the whole
concern of this project is that metrics over-punish displacement, that artefact dominates:
measured on vorticity, widths that rounded to 2, 3, 6 and 13 cells gave damage 0.0121, 0.0041,
0.0338 and 0.0880 — non-monotone, because the even severity level carried a half-cell shift the odd one did
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
| `lowpass_butterworth` | fraction of energy removed | Smooth rolloff; the ringing-free control for the above, and it resolves severity levels a sharp filter cannot |
| `highpass_ideal` | fraction of energy removed | Removes large scales. **Keeps the spatial mean deliberately** — deleting it removes a component four orders of magnitude larger than anything the cutoff controls, and before this was fixed every severity level gave an identical damage of 2.7e7 and the degradation carried no ordering at all |
| `highpass_butterworth` | fraction of energy removed | As above, smooth |

**The high-pass degradation has a narrow usable window on these fields, and that is a property of the
data.** Both filters are floored at the lowest usable cutoff, |k| = 1, and on density the modes
at that magnitude hold almost nothing while the diagonal modes just above them hold 69% of the
fluctuation energy. A mild request therefore resolves to a filter that passes essentially every
mode; one step harsher puts the damage already most of the way to an unrelated field.
The configured window is the widest measured — it spans a factor 3.4 in damage on vorticity and
gives density two usable severity levels of four — so the high-pass degradation alone does not reach the factor of
five that the other degradations do. No severity list fixes this; a field with more energy at high
wavenumbers would.
| `band_attenuate` | retained fraction | Damages one wavenumber band only. The direct test of whether a metric is scale-selective |

**Geometric** — the test for the double penalty. Shape and amplitude stay exactly correct;
only position changes.

| operator | severity | notes |
|---|---|---|
| `translate` | distance, cells | Whole-cell periodic shift. Quantised: the smallest step is one cell |
| `translate_subpixel` | distance, cells | Fractional shift by a Fourier phase ramp, exact on a periodic grid. Resolves the sub-cell region where metrics differ most, and reproduces `translate` at integer distances |
| `random_large_translation` | draw index | Not a severity level. Measures the unrelated-field anchor |

**Resolution.**

| operator | severity | notes |
|---|---|---|
| `coarsen` | factor | Conservative block average, then back to the fine grid |
| `subsample` | factor | Point-sampling instead, as the non-conservative control. At factor 8 this retains 102% of the variance where averaging retains 73%, because it folds small scales back in rather than removing them |

**Stochastic.**

| operator | severity | notes |
|---|---|---|
| `additive_noise` | fraction of fluctuation RMS | **Relative to the fluctuation, never the raw RMS.** Density here is 1.0 +/- 1.8e-4, so a fraction of the raw RMS would make even the mildest severity level total destruction |
| `multiplicative_noise` | relative | Error proportional to the local value |
| `gaussian_impostor` | — | Not a severity level. See Group B |

**Pointwise** — distortion applied to each cell's value on its own; the complement of
displacement, with correct position and wrong magnitude.

| operator | severity | notes |
|---|---|---|
| `gain` | relative | Scales the fluctuation, leaving the mean and every gradient's sign intact |
| `bias` | fraction of fluctuation RMS | A uniform offset, invisible to any metric built on fluctuations or gradients |
| `identity` | — | severity level 0 |

**Ensemble** — the ensemble is the wrong *width*, while its central prediction is
untouched. These apply only to a dataset that provides an ensemble, and they act on the
members: the reference the metrics are scored against is never degraded. Both scale the
members about their own mean, so the ensemble mean is preserved exactly and any metric
built on it alone is blind to this axis by construction — which is what makes these a
clean test of whether a metric sees calibration at all.

| operator | severity | notes |
|---|---|---|
| `spread_inflate` | fraction of the calibrated spread | Excess dispersion: the hedging forecast. Severity 1 doubles the spread |
| `spread_deflate` | fraction of the calibrated spread | Lost dispersion: the overconfident forecast. Severity 1 collapses the ensemble onto its mean |

They are two operators rather than one signed axis because the ladder sorts each
operator's severities into one order of increasing damage, and dispersion error is least
damaging in the middle. Each axis is mildest at zero and worsens outward.

Any *other* operator — noise, bias, blur — applied to an ensemble dataset is applied to
each member independently, with an independent random draw per member where the operator
is stochastic. A single shared noise field would shift every member alike, which
translates the ensemble rather than perturbing it, and would leave the spread untouched.

---

## The figures

| figure | section | what it shows, and how to read it |
|---|---|---|
| `energy_spectrum` | 3 | Cumulative fluctuation energy against wavenumber, per field, with the applied spectral cutoffs drawn on. This sets the resolution of every filter's sequence of strengths: a spectral severity is a fraction of energy to remove and is converted to a cutoff using exactly this curve, so where the curve rises sharply neighbouring severity levels land on the same set of modes and become the same experiment. The density curve is almost a step — 3×10⁻⁵ of its fluctuation energy at or below |k| = 1 and 69% at |k| = √2 — which is why a sharp filter has only a couple of usable severity levels there; vorticity rises gradually, 50% by |k| = 3.2 and 99% by 51, and its cutoffs spread over more than a factor of ten. Dashed lines are cutoffs in use, dotted lines severity levels excluded for repeating a milder severity level or for doing nothing. It says nothing about phase — two fields with identical curves can look entirely different, which is the premise of the trap test above |
| `ladder_curves` | 3 | Value against severity level for every degradation, with an interquartile band over frames. The curve the correlation summarises. Flat means blind to that failure mode |
| `monotonicity_heatmap` | 4 | `rho` for every metric against every degradation. Down a column: is this metric monotone? Across a row: what does it detect? Hatched cells fall below the reference value |
| `severity_level_separation` | 5 | The spread of each severity level across frames, as violins. Where neighbouring violins overlap, the metric cannot rank models one severity level apart |
| `field_gallery` | 6 | The per-cell contribution to the metric, on **shared colour limits**. Autoscaling each panel would make a heavily smoothed field look identical to the reference. A displaced feature shows as two lobes — one where it should be and is not, one where it is and should not be |
| `selectivity_profile` | 7 | Each metric's response across every degradation, as grouped bars. Needs two or more metrics |
| `deception_panel` | 8 | Damage assigned to the Gaussian field (star) against the ordinary severity levels (open circles). A star near zero means the metric sees only second-order statistics |
| `displacement_response` | 9 | Damage against displacement distance, log x. Shape and amplitude are exactly correct at every point on this curve; only position changes. The project's central figure |
| `cost_frontier` | 10 | Worst-degradation correlation against cost. Upper left is useful; upper right is right-but-unaffordable, so a diagnostic rather than a loss |

Every figure has a CSV of exactly the numbers plotted, in `data/figure_data/`. No number
appears in the report without a machine-readable source in the same folder.

---

## Glossary

**Double penalty.** A sharp feature that is correct in shape and amplitude but slightly
displaced is penalised twice by a metric that compares fields one cell at a time: once for
being absent where it should be, and once for being present where it should not. The name
comes from weather forecast verification; the same problem is called cycle skipping in
seismic imaging.

**Phase-blind.** Sensitive only to how much energy sits at each scale, and not at all to
where anything is in the domain. A phase-blind metric cannot distinguish a structured
turbulent field from a Gaussian one with the same energy spectrum.

**Intermittency.** The tendency of turbulent quantities to have heavy-tailed distributions —
rare, intense events. Measured here by flatness, which is 3 for a Gaussian field and about 17
for our vorticity. It is the first property an over-smoothed surrogate destroys and the last
one a metric comparing fields cell by cell notices.

**Flatness.** The fourth moment normalised by the square of the second,
mean(x^4) / mean(x^2)^2. Exactly 3 for a Gaussian.

**Reference, or clean.** Severity level 0: the undamaged field.

**Unrelated field.** A field with identical statistics and no positional alignment. Defines
D = 1.

**Primitive and derived fields.** Density and velocity are stored and are remapped directly.
Vorticity and pressure are computed from them, and are recomputed after any remap rather than
averaged.
