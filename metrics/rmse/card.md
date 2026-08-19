---
name: rmse
kind: metric
---

## Definition

For fields $f$ (reference) and $g$ (candidate) on the same analysis grid, with $C$
channels and $N$ cells per channel,

$$
\mathrm{RMSE}(f, g) = \sqrt{\frac{1}{CN} \sum_{c=1}^{C} \sum_{i=1}^{N}
\bigl( f_{c,i} - g_{c,i} \bigr)^2} \tag{1}
$$

that is, the square root of the mean squared error. For a vector field the channels are
pooled rather than reduced separately, and the uniform analysis grid gives every cell
equal weight.

The square root is a monotone function, so Equation (1) orders any set of candidates
exactly as the mean squared error does. It changes the units and the spacing between
scores, never the ranking.

The per-cell map stored beside the scalar is the *squared* error, and the declared
reduction is therefore `sqrt_mean` rather than `mean`: averaging the map gives the mean
squared error, and the metric is the square root of that.

### Boundary handling

None. The operation is local to each cell, so no neighbourhood is ever consulted and no
boundary condition can enter.

## Performance

<!-- GENERATED performance: written by `python -m fmeval.cards evidence rmse`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence rmse`.

<!-- END GENERATED performance -->

## Intuition

Root mean squared error is the mean squared error carried back into the units of the
field. Squaring the differences, averaging, then taking the square root gives a number
that reads like a typical error size rather than a typical error size squared, which is
the only reason to prefer it to the squared form.

Because the square root is monotone, it can never disagree with the mean squared error
about which of two candidates is better. Whatever ranking one produces, the other
produces too. What changes is the spacing: on a four-by-four grid, with one candidate
that moved a bright square by a cell and another that halved its brightness,

```
reference        moved one cell    half brightness
0 0 0 0          0 0 0 0           0    0    0    0
0 1 1 0          0 0 1 1           0   0.5  0.5   0
0 1 1 0          0 0 1 1           0   0.5  0.5   0
0 0 0 0          0 0 0 0           0    0    0    0

                 rmse = 0.5        rmse = 0.25
```

the displaced candidate scores twice the damped one, where the squared error made it four
times. The underlying preference is identical; the square root simply compresses it.

What it ignores is everything the squared error ignores: the arrangement of the errors,
and therefore position.

## Reading the output

The value runs from zero upwards with no upper limit, in the field's own units, so
numbers from a density field and a vorticity field cannot be compared. Lower is better,
and zero means the fields are identical cell for cell. It is directly readable as an error
size, which is what recommends it over the squared form for reporting.

There is no value that counts as good in the abstract; it depends on the variance of the
field being predicted, which is why the suite reports damage alongside it.

Comparisons across models on the same field, dataset and analysis grid are the intended
use. Comparisons across fields need normalising — that is what NRMSE is for. Comparisons
across resolutions are invalid as they stand, because the mean over cells reweights the
small scales when the grid is refined; compare on a common analysis grid.

One comparison to make carefully: ranking models by RMSE and by MSE always agrees, so
reporting both adds no information about which model is better.

## Limitations

Sharing an ordering with mean squared error means sharing every blind spot it has. A
displaced feature is penalised twice, once where it should be and once where it is, and
the response to sub-cell displacement is quadratic — RMSE inherits that even though its
own numbers look linear, because the square root is applied after the average, not per
cell. Reading the score as though it responded linearly to displacement is the mistake
this metric invites.

It also cannot be compared across fields with different units, and the stored per-cell map
does not average to the metric value, which will silently mislead any consumer that
assumes it does.

## Results

<!-- GENERATED run: written by `python -m fmeval.cards evidence rmse`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence rmse`.

<!-- END GENERATED run -->

Each subsection links to the degradations it reports; what those degradations do, and what
their severity numbers mean, is documented in their own bundles.

### Smoothing

[gaussian_blur](../../degradations/gaussian_blur/card.md) ·
[box_blur](../../degradations/box_blur/card.md) ·
[median_blur](../../degradations/median_blur/card.md)

<!-- GENERATED results_smoothing: written by `python -m fmeval.cards evidence rmse`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence rmse`.

<!-- END GENERATED results_smoothing -->

### Spectral filtering

[lowpass_ideal](../../degradations/lowpass_ideal/card.md) ·
[lowpass_butterworth](../../degradations/lowpass_butterworth/card.md) ·
[highpass_ideal](../../degradations/highpass_ideal/card.md) ·
[highpass_butterworth](../../degradations/highpass_butterworth/card.md)

<!-- GENERATED results_spectral: written by `python -m fmeval.cards evidence rmse`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence rmse`.

<!-- END GENERATED results_spectral -->

### Displacement

[translate_x](../../degradations/translate/card.md) ·
[translate_subpixel](../../degradations/translate_subpixel/card.md)

<!-- GENERATED results_geometric: written by `python -m fmeval.cards evidence rmse`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence rmse`.

<!-- END GENERATED results_geometric -->

The ordering is identical to mean squared error, by construction. The numbers are its
square root, so the response to sub-cell displacement is still quadratic underneath even
though the reported values change more gently.

### Resolution loss

[coarsen](../../degradations/coarsen/card.md)

<!-- GENERATED results_resolution: written by `python -m fmeval.cards evidence rmse`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence rmse`.

<!-- END GENERATED results_resolution -->

### Noise

[additive_noise](../../degradations/additive_noise/card.md)

<!-- GENERATED results_stochastic: written by `python -m fmeval.cards evidence rmse`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence rmse`.

<!-- END GENERATED results_stochastic -->

### Canaries

[gaussian_impostor](../../degradations/gaussian_impostor/card.md) ·
[uncorrelated](../../degradations/random_large_translation/card.md)

<!-- GENERATED results_canaries: written by `python -m fmeval.cards evidence rmse`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence rmse`.

<!-- END GENERATED results_canaries -->

### Across the ladder

<!-- GENERATED results_summary: written by `python -m fmeval.cards evidence rmse`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence rmse`.

<!-- END GENERATED results_summary -->

RMSE agrees with MSE on every ordering across the ladder, which is what the near-unit rank
correlation between the pointwise controls reflects. Reporting both is redundant for
ranking; the choice between them is a choice of units.

## References

\bibliography
