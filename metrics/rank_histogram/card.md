---
name: rank_histogram
kind: metric
---

## Definition

At every channel and cell, sort the $M$ ensemble members and record where the reference
falls among them. The rank is the number of members below it,

$$
r_{c,i} = \#\{ m : x_{m,c,i} < y_{c,i} \} \in \{0, 1, \dots, M\} \tag{1}
$$

giving $M+1$ possible outcomes, one for each gap in the sorted ensemble including the two
open ends. Collect these over all channels and cells of the frame into a histogram with
$M+1$ bins and let $f_k$ be the fraction in bin $k$. The reported scalar is the
**reliability index**, the total absolute departure from flat [@dellemonache2006]:

$$
\Delta = \sum_{k=1}^{M+1} \Bigl| f_k - \frac{1}{M+1} \Bigr| \tag{2}
$$

If the ensemble is a genuine sample from the distribution the reference was drawn from, then
the reference is exchangeable with the members and equally likely to occupy any of the
$M+1$ positions, so $\mathbb{E} f_k = 1/(M+1)$ and $\Delta$ is zero up to sampling noise
[@anderson1996; @hamill2001]. The index is bounded: $\Delta = 0$ for a flat histogram and
$\Delta = 2M/(M+1)$ when every draw lands in a single bin, which approaches 2 for a large
ensemble.

**Ties are broken at random.** Where several members equal the reference exactly, Equation
(1) is ambiguous, and resolving it by counting only members strictly below would place every
tied draw in the lowest bin and manufacture a spike that reads as bias. The rank is instead
drawn uniformly from the range the tie spans [@hamill2001], using the seeded generator the
pipeline supplies, so a run remains reproducible. This matters for a collapsed ensemble and
for any coarsely quantised field.

The histogram is formed **per frame**, not pooled across frames. Pooling would average away
a calibration failure that changes sign along the trajectory, and it is the same rule the
rank correlations in this suite follow for the same reason.

A chi-square goodness-of-fit statistic would be the other natural summary, and is used in
this bundle's tests where the draws really are independent. It is not what is reported: its
scale depends on the bin count and the sample size, so it cannot be compared across ensemble
sizes or grids, and interpreting it as a test would need an independence assumption these
spatially correlated fields do not satisfy. Equation (2) is descriptive, bounded, and reads
the same way at any ensemble size.

### Boundary handling

None in space: the rank at a cell uses only that cell's values across the ensemble. The
"boundary" that does need a rule is at the ends of the rank ordering, and ties are handled
as described above.

## Performance

<!-- GENERATED performance: written by `python -m fmeval.cards evidence rank_histogram --results results/rank_histogram_1787800137`, do not edit -->

| test family | field | degradations | rank correlation | weakest gap between neighbouring strengths | first strength detected |
|---|---|---|---|---|---|
| Ensemble dispersion | density | 2 | 1 to 1 | 1 | level 1 |
| Cell-value distortion | density | 1 | 1 to 1 | 1 | level 2 |

One row per family of degradation and physical field. **Rank correlation** asks whether the metric put the strengths of one degradation in the right order: it is the Spearman correlation between the metric and the applied strength, computed inside a single frame, and the column gives the range over the degradations in that family. A value of 1 means every strength was ordered correctly in every frame. **Weakest gap between neighbouring strengths** asks whether the metric can tell one strength from the next: it is the smallest Mann-Whitney overlap between any two neighbouring strengths, where 1 means the two never overlap and 0.5 means the metric cannot separate them at all. **First strength detected** is the mildest strength at which the metric has moved a tenth of the way from the undegraded reference toward a field with no relation to the truth; a dash means the metric never reached that tenth. **Damage** is that same 0-to-1 scale read as a number: 0 is the undegraded reference and 1 is an unrelated field.

This table reports what was measured and grades none of the measurements. What the numbers mean for this metric is written in the subsections below, beside the test that produced each number.

<!-- END GENERATED performance -->

## Intuition

Line the ensemble members up in order at one point in the field and ask where the true value
sits among them. Repeat that everywhere and count how often the truth came last, second to
last, and so on down to first. If the ensemble is honest, the truth is just one more draw
from the same distribution, so it is equally likely to land in any of the slots and the
counts come out flat. This metric measures how far from flat they came out.

What makes the diagnostic worth more than a single ratio is that the *shape* of the
departure names the fault. If the members huddle too closely together, the truth keeps
falling outside them and the counts pile up at both ends — a U. If they are spread too
widely, the truth is usually caught somewhere in the middle and the counts pile up there — a
dome. If the whole ensemble is offset, the counts slope to one side. The reported number
collapses that shape to a single magnitude, so it says how badly without saying which; the
histogram itself, if you plot it, says which.

The property that earns this metric its place beside the others is that it responds to
changes nothing built on the ensemble mean can see. Squeezing an ensemble toward its own
centre leaves that centre exactly where it was, so any mean-based score is unchanged, while
the truth starts falling outside the members and this index rises immediately. A test in
this bundle pins that contrast directly.

A worked example with three members and four cells, arranged so the reference takes each
possible rank exactly once:

```
reference        members (three per cell)      result
0 0 0 0          per cell, one rank each        0.0
```

Four cells and four bins with one draw each is a perfectly flat histogram, so the index is
zero.

It ignores magnitude entirely. Only the ordering matters, so an ensemble can be wrong by any
amount and still be perfectly calibrated by this measure.

## Reading the output

The value is dimensionless and runs from zero to just under 2, with zero the best. There is
no target other than zero, so unlike the spread-to-skill ratio this reads like an ordinary
error metric: lower is better and the ordering statistics apply directly.

What counts as small depends on the sample, and this is the number people get wrong. Even a
perfectly calibrated ensemble produces a non-zero index, because a finite histogram is never
exactly flat; the floor scales roughly as the square root of the bin count over the number
of draws. On the synthetic ensemble here, with a few thousand cells and eight members, that
floor is around 0.1. Compare a measured value against that floor rather than against zero,
and the cheapest way to establish the floor is to read this metric at the clean severity
level of the same run.

Because ranks are invariant to any monotone rescaling of the field, the metric is scale free
and comparable across fields of wildly different magnitude. Comparison across ensemble sizes
is meaningful in the sense that the bound is nearly the same, but the sampling floor is not,
so a small index on a four-member ensemble is weaker evidence than the same index on fifty.
Comparison across resolutions changes the number of draws and therefore the floor.

## Limitations

The index says how far from calibrated an ensemble is but not in which direction, and the two
directions have opposite remedies: a U-shaped histogram means widen the ensemble, a dome
means narrow it. Reading only this number, a user cannot tell which. `spread_skill`, whose
sign carries exactly that information, is its natural companion.

The aggregate hides spatial structure. An ensemble that is overconfident in one region and
overdispersed in another can produce a histogram that is flat overall, and this metric will
report a well-calibrated prediction. The failure is invisible to any whole-field summary.

The sampling floor is a trap in the other direction. Because the index is bounded below by
the noise of a finite histogram rather than by zero, a small positive value proves nothing
on its own, and comparing a value measured on a coarse grid against one from a fine grid
compares two different floors. The effective number of independent draws is also far smaller
than the cell count on these fields, since neighbouring cells of a turbulent flow are
strongly correlated — so the true floor is higher than an independence assumption would
suggest, and the value is noisier frame to frame than the raw count of cells implies.

## Results

<!-- GENERATED run: written by `python -m fmeval.cards evidence rank_histogram --results results/rank_histogram_1787800137`, do not edit -->

Measured on `synthetic_ensemble`, frames 0 to 11 (12 frames of developed flow), on the 64 analysis grid, seed 20260807, at commit `c49b363765d7` (working tree dirty). Run `rank_histogram_1787800137`.

Every number in this section comes from that one run. Regenerate with `python -m fmeval.cards evidence <name> --results results/rank_histogram_1787800137`.

<!-- END GENERATED run -->

**What these numbers are evidence of, and what they are not.** The run behind them is on
`synthetic_ensemble`, which is generated rather than simulated: the reference is drawn from
the same process as the members, with the same dispersion, so the two are exchangeable and
every quantity below has a value derivable in advance. That is what makes the run worth
citing — an estimator agreeing with arithmetic it could not have fitted to is a real
result, and it is the claim a first implementation has to establish.

It is not evidence about turbulence. The fields have no shocks, no intermittency and no
coherent structure, so nothing here says how this metric behaves on the flows this
repository exists to evaluate. The degradation families a physical run would exercise —
smoothing, spectral filtering, displacement, resolution loss — are absent from these
tables for that reason, and so are the trap tests. When an ensemble of real runs exists
([issue 004](../../issues/004-independent-realizations.md)), this card should be
regenerated against it and this section will say something different.

### Ensemble dispersion

[spread_inflate](../../degradations/spread_inflate/card.md) ·
[spread_deflate](../../degradations/spread_deflate/card.md)

<!-- GENERATED results_ensemble: written by `python -m fmeval.cards evidence rank_histogram --results results/rank_histogram_1787800137`, do not edit -->

| degradation | field | strengths | rank correlation | fraction of frames in the right order | weakest gap between neighbouring strengths |
|---|---|---|---|---|---|
| `spread_deflate` | density | 4 | 1 | 1 | 1 |
| `spread_inflate` | density | 4 | 1 | 1 | 1 |

<!-- END GENERATED results_ensemble -->

The clean ensemble reads 0.049, which is the sampling floor rather than zero: 16 members
over a 64x64 grid give 17 bins and a finite histogram is never exactly flat. Every measured
departure below should be read against 0.049, not against zero.

Both directions rise well clear of it — to 1.239 at the harshest deflation and 1.009 at the
harshest inflation, a factor of 20 or more — with a rank correlation of 1 on each. The
index cannot say which direction it saw, and that is the limitation stated above made
concrete: 1.0 could be either fault, and only `spread_skill`'s side of one distinguishes
them.

Deflation registers more strongly than inflation at comparable severity, which follows from
the shapes: an over-narrow ensemble pushes the truth outside the members entirely, piling
draws into the two end bins, while an over-wide one merely concentrates them toward the
middle and leaves every bin occupied.

## References

\bibliography
