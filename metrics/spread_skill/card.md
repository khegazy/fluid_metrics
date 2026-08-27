---
name: spread_skill
kind: metric
---

## Definition

Two quantities are compared. The **spread** is the square root of the mean ensemble
variance, where the variance at each cell is the unbiased sample variance over the $M$
members,

$$
\sigma^2_{c,i} = \frac{1}{M-1}\sum_{m=1}^{M}
\bigl( x_{m,c,i} - \bar{x}_{c,i} \bigr)^2 ,
\qquad
s = \sqrt{ \frac{1}{CN} \sum_{c,i} \sigma^2_{c,i} } \tag{1}
$$

The **skill** is the root mean squared error of the ensemble mean,

$$
e = \sqrt{ \frac{1}{CN} \sum_{c,i}
\bigl( \bar{x}_{c,i} - y_{c,i} \bigr)^2 } \tag{2}
$$

and the reported value is their ratio, corrected for ensemble size:

$$
\mathrm{SSR} = \sqrt{\frac{M+1}{M}} \; \frac{s}{e} \tag{3}
$$

**The order of the square root and the average in Equation (1) is the whole point.** The
spread must be the square root of the *average variance*, not the average of the per-cell
standard deviations. The two differ by Jensen's inequality whenever the variance is not
constant across cells, always in the same direction: the average of square roots is smaller,
so the naive form understates the spread and manufactures a diagnosis of underdispersion
that is not there. Fortin and colleagues show this changed an operational verdict from
"underdispersed" to "excellent agreement, with possible overdispersion at long lead times"
[@fortin2014]. On the two-cell example in this bundle's tests the two forms differ by a
factor of $\sqrt{2}$.

The correction factor in Equation (3) has the same origin. Under exchangeability — the
reference being statistically just another member — the expected squared error of a mean of
$M$ members exceeds the ensemble variance by $(M+1)/M$, because the mean carries its own
sampling error. Without the factor a perfectly calibrated four-member ensemble would read
0.89 and a fifty-member one 0.99, and the two could not be compared; with it both read one
[@fortin2014].

Two edge cases are defined rather than left to floating point. A collapsed ensemble with an
exact mean gives $0/0$ and returns zero, the value of maximal overconfidence. A non-degenerate
ensemble whose mean happens to be exact gives $s/0$ and returns positive infinity, which is
the honest answer — the dispersion is unboundedly larger than the error — rather than a large
finite number that would read as a measurement.

### Boundary handling

None. Variance over members and the mean over cells are both pointwise; no cell consults a
neighbour, so the domain edge never enters.

## Performance

<!-- GENERATED performance: written by `python -m fmeval.cards evidence <name>`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence <name>`.

<!-- END GENERATED performance -->

## Intuition

A prediction that comes with a stated uncertainty is making two claims: this is roughly what
will happen, and this is roughly how wrong I expect to be. This metric checks the second
claim against the first. It compares how much the members disagree with each other against
how far their consensus actually landed from the truth. If a forecast says it is uncertain
by about this much, and it turns out to be wrong by about that much, the two should match.

The mechanism is a statistical identity rather than a convention. If an ensemble really is a
sample from the distribution the truth was drawn from, then the truth is just another member,
and the typical distance from the mean to a member is the same as the typical distance from
the mean to the truth. So the ratio is one — not approximately, but as an expectation, once
the correction for finite ensemble size is applied.

The characteristic failures are named by which side of one the value falls. Below one the
members agree with each other more than they agree with reality: the forecast is
overconfident, which is the dangerous direction, because a confident wrong answer invites
action. Above one the members disagree more than necessary: the forecast hedges, which is
merely wasteful.

A worked example on a single cell, three members against a reference of 2:

```
reference        members              result
2                -1, 0, 1             0.5774
```

The sample variance of the members is 1, so the raw spread is 1; the three-member correction
multiplies it to 1.1547. The ensemble mean is 0 against a reference of 2, so the skill is 2.
The ratio is 0.577 — the ensemble claims about half the uncertainty its error warrants.

What it ignores is accuracy. An ensemble can be badly wrong and perfectly calibrated at the
same time, as long as it is honest about being wrong, and this metric will report one.

## Reading the output

The value is dimensionless, runs from zero upward, and — unlike almost everything else in
this suite — **is not better when smaller**. One is the target. Below one the ensemble is
overconfident, above one it hedges, and the distance from one in either direction is what
says how badly. Zero, from an ensemble collapsed onto a single field, is the worst
attainable value, not the best.

That has a consequence for how this suite ranks the metric, and it is worth stating plainly
because the number in the table and the number in the ranking are not the same. The value
reported everywhere is the raw ratio, as the forecast-verification literature reports it, so
that reading 0.4 tells you directly that the ensemble is too narrow. The ordering statistics
— the rank correlation, monotonicity, sensitivity — are computed on the distance from the
target instead, since a quantity that is wrong in two directions cannot be ranked as though
it were wrong in one. See "Metrics with a target value" in `TEST_DESCRIPTION.md`.

As a rough guide, values within about 0.9 to 1.1 are usually treated as well calibrated in
operational forecasting, but that band is a convention rather than a threshold and depends
on the ensemble size and the sample. Because the metric is a ratio of two quantities in the
same units, it is scale free, which makes it directly comparable across fields whose
magnitudes differ by orders of magnitude — density and vorticity, say — in a way that none
of the error metrics here are. Comparison across ensemble sizes is valid because of the
correction in Equation (3). Comparison across resolutions is weaker: both spread and error
change with the analysis grid, and not necessarily together.

## Limitations

The metric is silent about accuracy, and this is the failure to watch for. An ensemble whose
members are all wrong in the same way, but honestly spread about their wrong consensus, reads
as perfectly calibrated. Read alone it would call such a prediction good. It belongs next to
`ensemble_mean_rmse` or `crps`, never instead of them.

The ratio is also an aggregate over the whole field, so it can be right on average and wrong
everywhere. An ensemble that is badly overconfident in the half of the domain containing a
shock and compensatingly overdispersed in the smooth half averages to one and is reported as
calibrated. Nothing in a single number can detect that; `rank_histogram` will not detect it
either, for the same reason, and only a spatially resolved diagnostic would.

Finally, calibration measured against a single reference realization is a statement about a
sample, not a proof. With few cells or a strongly correlated field the effective sample size
is much smaller than the cell count suggests, and the ratio is correspondingly noisy. Spatial
correlation in these fields is strong, so treat small departures from one as sampling noise
unless they persist across frames.

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

What the dispersion axes found. These two axes are the ones this metric exists to detect, so
a clean monotone response on both — rising above one on inflation, falling below one on
deflation — is the minimum bar rather than a result.

## References

\bibliography
