---
name: ensemble_mean_rmse
kind: metric
---

## Definition

For an ensemble $x_{1} \dots x_{M}$ and a reference $y$, both on the analysis grid with $C$
channels and $N$ cells per channel, collapse the ensemble to its mean and score that:

$$
\bar{x}_{c,i} = \frac{1}{M}\sum_{m=1}^{M} x_{m,c,i} \tag{1}
$$

$$
\mathrm{RMSE}_{\bar{x}} = \sqrt{ \frac{1}{CN} \sum_{c=1}^{C} \sum_{i=1}^{N}
\bigl( \bar{x}_{c,i} - y_{c,i} \bigr)^2 } \tag{2}
$$

The order of the two operations is the whole content of the definition. Averaging the
members first and scoring second, as in Equations (1) and (2), is not the same as scoring
each member and averaging the scores: by Jensen's inequality the second is never smaller,
and the gap is exactly the ensemble variance. What is reported here is the error of the
consensus, not the typical error of a member.

The implementation calls this repository's `rmse` on the member mean rather than repeating
the sum, so the two cannot drift apart; a test asserts the equality.

### Boundary handling

None. Both the mean over members and the mean over cells are taken pointwise, so no cell
consults its neighbours and the domain edge never enters.

## Performance

<!-- GENERATED performance: written by `python -m fmeval.cards evidence <name>`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence <name>`.

<!-- END GENERATED performance -->

## Intuition

This measures how good an ensemble's single best guess is, and deliberately nothing else.
Average the members together into one field, then score that field the ordinary way. It is
the number to quote when someone asks what happens if you ignore the uncertainty and just
use the prediction.

Its value on the panel comes from what it refuses to see. Widening or narrowing an ensemble
about its own centre does not move this number at all — a test in this bundle pins that
across a factor of fifty in spread. So when it and a probabilistic score disagree, the
disagreement is informative: if this stays put while CRPS rises, the ensemble's centre is
fine and its uncertainty has gone wrong. If both rise together, the prediction itself has
drifted.

There is a second, less obvious reason the number is worth having. Averaging is a smoothing
operation, so the ensemble mean is systematically flatter than any of its members. On a
turbulent field that means the consensus can score better on this metric than any individual
member does, while looking less like real turbulence than any of them — the mean of many
plausible flows is not itself a plausible flow. A model tuned to this number alone will
learn to blur.

A worked example, two members against a reference of 1 on a small uniform field:

```
reference        members              result
1 1              0 0    and   4 4     1.0
1 1              0 0          4 4
```

The mean of 0 and 4 is 2 everywhere, the error is 1 everywhere, and the root mean square of
that is 1. Note that each member individually is off by 1 and 3 respectively, so the typical
member error is 2 — twice what the consensus achieves.

It ignores dispersion entirely, and therefore cannot distinguish a confident prediction from
a vague one.

## Reading the output

The value is in the field's own units, runs from zero upward with no upper bound, and lower
is better. Zero means the ensemble mean matched the reference exactly.

What counts as good depends entirely on the field's own scale, so the number is only
meaningful in comparison. The most useful comparison is against `rmse` computed on a
deterministic prediction of the same system: if an ensemble's consensus cannot beat a single
deterministic run, the ensemble is not earning its cost.

Comparisons across models on one dataset are valid. Comparisons across resolutions are not
directly, since the metric is resolution dependent. Comparison across ensemble sizes is
valid but requires care in interpretation rather than in the estimator: the mean of more
members is smoother, so this number tends to improve with ensemble size for reasons that
have nothing to do with the model being better.

## Limitations

The metric is blind to uncertainty by construction, which is its purpose and also its
principal danger: a model that reports a wildly overconfident ensemble and one that reports
an honest one score identically here. It must not be read alone on a probabilistic panel.

It rewards smoothing. Because the ensemble mean of a set of plausible turbulent fields is
smoother than any of them, this metric prefers a blurred consensus to a sharp one even when
the sharp members are individually more realistic. That is the same pathology that makes
mean squared error a poor training loss for turbulence, arriving by a different route.

And it inherits every blindness of the pointwise family: it compares each cell with the same
cell, so a consensus that is correct in shape but slightly displaced is penalised twice, once
for the missing feature and once for the spurious one.

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

What the dispersion axes found. This metric is expected to be flat on both of them, since
they preserve the ensemble mean exactly; a flat response here is the control working, not a
failure to detect anything.

## References

\bibliography
