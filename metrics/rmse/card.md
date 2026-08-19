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

<!-- GENERATED performance: written by `python -m fmeval.cards evidence rmse --results results/comparison_1787115827`, do not edit -->

| test | field | axes | rank correlation | weakest separation | first detected |
|---|---|---|---|---|---|
| geometric | density | 2 | 1 to 1 | 0.959 | level 3 |
| geometric | velocity | 2 | 1 to 1 | 0.984 | level 4 |
| geometric | vorticity | 2 | 1 to 1 | 0.754 | level 1 |
| resolution | density | 1 | 1 to 1 | 0.96 | level 4 |
| resolution | velocity | 1 | 1 to 1 | 1 | level — |
| resolution | vorticity | 1 | 1 to 1 | 0.741 | level 1 |
| smoothing | density | 3 | 1 to 1 | 0.955 | level 3 |
| smoothing | velocity | 3 | 1 to 1 | 0.986 | level 3 |
| smoothing | vorticity | 3 | 1 to 1 | 0.69 | level 2 |
| spectral | density | 4 | 1 to 1 | 0.698 | level 1 |
| spectral | velocity | 4 | 1 to 1 | 0.993 | level 1 |
| spectral | vorticity | 4 | 1 to 1 | 0.62 | level 1 |
| stochastic | density | 1 | 1 to 1 | 1 | level 4 |
| stochastic | velocity | 1 | 1 to 1 | 1 | level 4 |
| stochastic | vorticity | 1 | 1 to 1 | 1 | level 4 |
| canary: phase-randomised impostor | density | 1 | — | — | damage 1.11 |
| canary: phase-randomised impostor | velocity | 1 | — | — | damage 0.813 |
| canary: phase-randomised impostor | vorticity | 1 | — | — | damage 0.95 |

Rank correlation is the per-frame Spearman correlation of the metric with severity, reported as the range over the axes in that family; 1 means every severity ordered correctly in every frame. Weakest separation is the smallest Mann-Whitney overlap between neighbouring severities. First detected is the lowest severity level at which the metric departs from clean by a tenth of the distance to an unrelated field. Damage is on that same scale: 0 is the reference and 1 is an unrelated field.

This table reports what was measured and grades none of it. What the numbers mean for this metric is in the subsections below, beside the test that produced each.

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

What this metric ignores is everything the squared error ignores: the arrangement of the
errors, and therefore position.

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

Sharing an ordering with mean squared error means sharing every blind spot mean squared
error has. A displaced feature is penalised twice, once where it should be and once where
it is, and the response to sub-cell displacement is quadratic — RMSE inherits that even
though its own numbers look linear, because the square root is applied after the average,
not per cell. Reading the score as though it responded linearly to displacement is the
mistake this metric invites.

It also cannot be compared across fields with different units, and the stored per-cell map
does not average to the metric value, which will silently mislead any consumer that
assumes it does.

## Results

<!-- GENERATED run: written by `python -m fmeval.cards evidence rmse --results results/comparison_1787115827`, do not edit -->

Measured on `kinet_re5e4`, frames 2000 to 10000 (161 frames of developed flow), on the 256 analysis grid, seed 20260807, at commit `85ddd3788061` (working tree dirty). Run `comparison_1787115827`.

Every number in this section comes from that one run. Regenerate with `python -m fmeval.cards evidence <name> --results results/comparison_1787115827`.

<!-- END GENERATED run -->

Each subsection links to the degradations that subsection reports. What those degradations
do, and what their strength numbers mean, is documented on their own pages.

### Smoothing

[gaussian_blur](../../degradations/gaussian_blur/card.md) ·
[box_blur](../../degradations/box_blur/card.md) ·
[median_blur](../../degradations/median_blur/card.md)

<!-- GENERATED results_smoothing: written by `python -m fmeval.cards evidence rmse --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `box_blur` | density | 4 | 1 | 1 | 0.955 |
| `box_blur` | velocity | 4 | 1 | 1 | 1 |
| `box_blur` | vorticity | 4 | 1 | 1 | 0.69 |
| `gaussian_blur` | density | 4 | 1 | 1 | 0.96 |
| `gaussian_blur` | velocity | 4 | 1 | 1 | 1 |
| `gaussian_blur` | vorticity | 4 | 1 | 1 | 0.749 |
| `median_blur` | density | 3 | 1 | 1 | 0.972 |
| `median_blur` | velocity | 3 | 1 | 1 | 0.986 |
| `median_blur` | vorticity | 3 | 1 | 1 | 0.86 |

<!-- END GENERATED results_smoothing -->

### Spectral filtering

[lowpass_ideal](../../degradations/lowpass_ideal/card.md) ·
[lowpass_butterworth](../../degradations/lowpass_butterworth/card.md) ·
[highpass_ideal](../../degradations/highpass_ideal/card.md) ·
[highpass_butterworth](../../degradations/highpass_butterworth/card.md)

<!-- GENERATED results_spectral: written by `python -m fmeval.cards evidence rmse --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `highpass_butterworth` | density | 4 | 1 | 1 | 0.72 |
| `highpass_butterworth` | velocity | 3 | 1 | 1 | 1 |
| `highpass_butterworth` | vorticity | 4 | 1 | 1 | 0.633 |
| `highpass_ideal` | density | 3 | 1 | 1 | 0.698 |
| `highpass_ideal` | velocity | 2 | 1 | 1 | 1 |
| `highpass_ideal` | vorticity | 4 | 1 | 1 | 0.62 |
| `lowpass_butterworth` | density | 4 | 1 | 1 | 0.852 |
| `lowpass_butterworth` | velocity | 3 | 1 | 1 | 1 |
| `lowpass_butterworth` | vorticity | 4 | 1 | 1 | 0.684 |
| `lowpass_ideal` | density | 3 | 1 | 1 | 0.951 |
| `lowpass_ideal` | velocity | 2 | 1 | 1 | 0.993 |
| `lowpass_ideal` | vorticity | 4 | 1 | 1 | 0.685 |

<!-- END GENERATED results_spectral -->

### Displacement

[translate_x](../../degradations/translate/card.md) ·
[translate_subpixel](../../degradations/translate_subpixel/card.md)

<!-- GENERATED results_geometric: written by `python -m fmeval.cards evidence rmse --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `translate_subpixel` | density | 6 | 1 | 1 | 0.964 |
| `translate_subpixel` | velocity | 6 | 1 | 1 | 0.984 |
| `translate_subpixel` | vorticity | 6 | 1 | 1 | 0.838 |
| `translate_x` | density | 5 | 1 | 1 | 0.959 |
| `translate_x` | velocity | 5 | 1 | 1 | 0.984 |
| `translate_x` | vorticity | 5 | 1 | 1 | 0.754 |

<!-- END GENERATED results_geometric -->

The ordering is identical to mean squared error, by construction. The numbers are its
square root, so the response to sub-cell displacement is still quadratic underneath even
though the reported values change more gently.

### Resolution loss

[coarsen](../../degradations/coarsen/card.md)

<!-- GENERATED results_resolution: written by `python -m fmeval.cards evidence rmse --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `coarsen` | density | 4 | 1 | 1 | 0.96 |
| `coarsen` | velocity | 4 | 1 | 1 | 1 |
| `coarsen` | vorticity | 4 | 1 | 1 | 0.741 |

<!-- END GENERATED results_resolution -->

### Noise

[additive_noise](../../degradations/additive_noise/card.md)

<!-- GENERATED results_stochastic: written by `python -m fmeval.cards evidence rmse --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `additive_noise` | density | 4 | 1 | 1 | 1 |
| `additive_noise` | velocity | 4 | 1 | 1 | 1 |
| `additive_noise` | vorticity | 4 | 1 | 1 | 1 |

<!-- END GENERATED results_stochastic -->

### Trap tests

[gaussian_impostor](../../degradations/gaussian_impostor/card.md) ·
[uncorrelated](../../degradations/random_large_translation/card.md)

<!-- GENERATED results_canaries: written by `python -m fmeval.cards evidence rmse --results results/comparison_1787115827`, do not edit -->

| field | impostor damage | nearest severity level | unrelated-field value |
|---|---|---|---|
| density | 1.11 | `lowpass_ideal=1.4029` | 0.0081 |
| velocity | 0.813 | `highpass_ideal=4.02293` | 0.0691 |
| vorticity | 0.95 | `translate_x=16` | 0.00381 |

Damage of 1 is what an unrelated field scores, so the impostor column says how close to useless this metric considers a field with the reference's spectrum and random phases. The nearest severity level names the ordinary degradation whose damage the impostor most resembles, which is the more legible statement of the same thing.

<!-- END GENERATED results_canaries -->

### Compared with the other metrics

<!-- GENERATED results_summary: written by `python -m fmeval.cards evidence rmse --results results/comparison_1787115827`, do not edit -->

| against | rank correlation across the ladder |
|---|---|
| `mse` | 1 |
| `mae` | 0.987 |
| `nrmse` | 0.979 |
| `enstrophy` | -0.108 |
| `kinetic_energy` | -0.23 |

Computed on the median value at each (axis, severity level), over every axis and field in the run, with the reference excluded. Two metrics correlating near 1 order the degradations alike; they may still weight them very differently, so this says they are redundant for ranking models rather than interchangeable as training losses.

<!-- END GENERATED results_summary -->

RMSE agrees with MSE on every ordering across every degradation, which is what the
near-unit rank correlation between the cell-by-cell baselines reflects. Reporting both is
redundant for ranking; the choice between them is a choice of units.

## References

\bibliography
