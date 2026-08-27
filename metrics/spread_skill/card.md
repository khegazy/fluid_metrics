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

<!-- GENERATED performance: written by `python -m fmeval.cards evidence spread_skill --results results/spread_skill_1787800137`, do not edit -->

| test family | field | degradations | rank correlation | weakest gap between neighbouring strengths | first strength detected |
|---|---|---|---|---|---|
| Ensemble dispersion | density | 2 | 1 to 1 | 1 | level 2 |
| Cell-value distortion | density | 1 | 1 to 1 | 1 | level 3 |

One row per family of degradation and physical field. **Rank correlation** asks whether the metric put the strengths of one degradation in the right order: it is the Spearman correlation between the metric and the applied strength, computed inside a single frame, and the column gives the range over the degradations in that family. A value of 1 means every strength was ordered correctly in every frame. **Weakest gap between neighbouring strengths** asks whether the metric can tell one strength from the next: it is the smallest Mann-Whitney overlap between any two neighbouring strengths, where 1 means the two never overlap and 0.5 means the metric cannot separate them at all. **First strength detected** is the mildest strength at which the metric has moved a tenth of the way from the undegraded reference toward a field with no relation to the truth; a dash means the metric never reached that tenth. **Damage** is that same 0-to-1 scale read as a number: 0 is the undegraded reference and 1 is an unrelated field.

This table reports what was measured and grades none of the measurements. What the numbers mean for this metric is written in the subsections below, beside the test that produced each number.

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

<!-- GENERATED run: written by `python -m fmeval.cards evidence spread_skill --results results/spread_skill_1787800137`, do not edit -->

Measured on `synthetic_ensemble`, frames 0 to 11 (12 frames of developed flow), on the 64 analysis grid, seed 20260807, at commit `c49b363765d7` (working tree dirty). Run `spread_skill_1787800137`.

Every number in this section comes from that one run. Regenerate with `python -m fmeval.cards evidence <name> --results results/spread_skill_1787800137`.

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
([issue 004](https://github.com/khegazy/pde_metrics/blob/main/issues/004-independent-realizations.md)), this card should be
regenerated against it and this section will say something different.

### Ensemble dispersion

[spread_inflate](../../degradations/spread_inflate/card.md) ·
[spread_deflate](../../degradations/spread_deflate/card.md)

<!-- GENERATED results_ensemble: written by `python -m fmeval.cards evidence spread_skill --results results/spread_skill_1787800137`, do not edit -->

| degradation | field | strengths | rank correlation | fraction of frames in the right order | weakest gap between neighbouring strengths |
|---|---|---|---|---|---|
| `spread_deflate` | density | 4 | 1 | 1 | 1 |
| `spread_inflate` | density | 4 | 1 | 1 | 1 |

<!-- END GENERATED results_ensemble -->

The clean ensemble reads 0.995, within half a percent of the exchangeable value of one,
which is the closed-form check on the estimator: the Fortin form and the sqrt((M+1)/M)
correction together land on the analytic answer at 16 members.

From there the axes separate cleanly in both directions — 0.199 at the harshest deflation
and 3.978 at the harshest inflation — with a rank correlation of 1 and no overlap between
neighbouring strengths on either. Note what that pair of numbers means for the ordering
statistics: the raw value moves *down* on one axis and *up* on the other, so both score 1
only because the analysis ranks on distance from the declared target rather than on the
value itself. A metric like this scored as an ordinary error would read −1 on one of its
two axes and look broken.

The bias axis is the useful contrast. It falls from 0.995 to 0.378 without any change in
dispersion at all, because biasing the members moves the ensemble mean away from the truth
and so inflates the denominator. A low ratio therefore does not by itself mean an
overconfident ensemble; it means spread and error disagree, and this axis is the reminder
that the error can be the thing that moved.

## References

\bibliography
