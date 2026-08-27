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

<!-- GENERATED performance: written by `python -m fmeval.cards evidence <name>`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence <name>`.

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

<!-- GENERATED run: written by `python -m fmeval.cards evidence <name>`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence <name>`.

<!-- END GENERATED run -->

No card in this repository may cite a run on `synthetic_ensemble_dev`, and that is
deliberate: `configs/cards/default.yaml` allows evidence only from the developed-flow
dataset, so that a number written into a card always describes a flow. The synthetic
ensemble validates this metric's estimator against a known answer, which is a different
claim and is recorded in the bundle's tests and in
[issue 003](../../issues/003-ensemble-data.md) instead.

These sections stay ungenerated until an ensemble of real runs exists
([issue 004](../../issues/004-independent-realizations.md)). What this metric does on
turbulence is not yet measured, and an empty section says so more honestly than a
synthetic number would.

### Ensemble dispersion

[spread_inflate](../../degradations/spread_inflate/card.md) ·
[spread_deflate](../../degradations/spread_deflate/card.md)

<!-- GENERATED results_ensemble: written by `python -m fmeval.cards evidence <name>`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence <name>`.

<!-- END GENERATED results_ensemble -->

What the dispersion axes found. Both directions should raise the index above its sampling
floor, since both destroy uniformity; the two are distinguished by the shape of the
histogram rather than by this number, so read them beside `spread_skill`.

## References

\bibliography
