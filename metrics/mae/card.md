---
name: mae
kind: metric
---

## Definition

For fields $f$ (reference) and $g$ (candidate) sampled on the same analysis grid, with $C$
channels and $N$ cells per channel,

$$
\mathrm{MAE}(f, g) = \frac{1}{CN} \sum_{c=1}^{C} \sum_{i=1}^{N}
\bigl| f_{c,i} - g_{c,i} \bigr| \tag{1}
$$

For a vector field the channels are pooled rather than reduced separately. The analysis
grid is uniform, so cells carry equal weight; on a non-uniform grid Equation (1) would
need cell volumes and would no longer be a plain mean.

Unlike the squared error, Equation (1) is a metric in the mathematical sense: it is the
L1 distance, and it satisfies the triangle inequality.

For a displacement $\delta$ small compared with the scale of variation, expanding
$f(x + \delta) - f(x) \simeq \delta\, \partial_x f$ in Equation (1) gives

$$
\mathrm{MAE} \simeq \delta \bigl\langle |\partial_x f| \bigr\rangle \tag{2}
$$

which is linear in the displacement where the squared error is quadratic. That single
difference in exponent is what separates the two in practice.

### Boundary handling

None. The operation is local to each cell, so no neighbourhood is ever consulted and no
boundary condition can enter.

## Performance

<!-- GENERATED performance: written by `python -m fmeval.cards evidence mae --results results/comparison_1787115827`, do not edit -->

| test | field | axes | rank correlation | weakest separation | first detected |
|---|---|---|---|---|---|
| geometric | density | 2 | 1 to 1 | 0.959 | level 3 |
| geometric | velocity | 2 | 1 to 1 | 0.96 | level 5 |
| geometric | vorticity | 2 | 1 to 1 | 0.795 | level 1 |
| resolution | density | 1 | 1 to 1 | 0.962 | level 4 |
| resolution | velocity | 1 | 1 to 1 | 1 | level — |
| resolution | vorticity | 1 | 1 to 1 | 0.942 | level 1 |
| smoothing | density | 3 | 1 to 1 | 0.963 | level 3 |
| smoothing | velocity | 3 | 1 to 1 | 0.977 | level 4 |
| smoothing | vorticity | 3 | 1 to 1 | 0.815 | level 2 |
| spectral | density | 4 | 0.5 to 1 | 0.192 | level 1 |
| spectral | velocity | 4 | 1 to 1 | 0.864 | level 1 |
| spectral | vorticity | 4 | 0.8 to 1 | 0.323 | level 1 |
| stochastic | density | 1 | 1 to 1 | 1 | level 3 |
| stochastic | velocity | 1 | 1 to 1 | 1 | level 4 |
| stochastic | vorticity | 1 | 1 to 1 | 1 | level 3 |
| canary: phase-randomised impostor | density | 1 | — | — | damage 1.36 |
| canary: phase-randomised impostor | velocity | 1 | — | — | damage 0.757 |
| canary: phase-randomised impostor | vorticity | 1 | — | — | damage 1.41 |

Rank correlation is the per-frame Spearman correlation of the metric with severity, reported as the range over the axes in that family; 1 means every severity ordered correctly in every frame. Weakest separation is the smallest Mann-Whitney overlap between neighbouring severities. First detected is the lowest severity level at which the metric departs from clean by a tenth of the distance to an unrelated field. Damage is on that same scale: 0 is the reference and 1 is an unrelated field.

This table reports what was measured and grades none of it. What the numbers mean for this metric is in the subsections below, beside the test that produced each.

<!-- END GENERATED performance -->

## Intuition

Mean absolute error compares two fields one cell at a time: subtract, take the size of
the difference regardless of sign, average. Taking the size rather than the square means
every unit of error counts the same wherever it appears, so one badly wrong cell and many
slightly wrong cells contribute in proportion to their total error rather than being
dominated by the worst. Nothing in the calculation looks beyond a single cell, so the
metric carries no notion of shape or position.

It shares that blindness with mean squared error and differs in how steeply it responds.
On a four-by-four grid, with one candidate that moved the bright square a cell and another
that halved its brightness where it stands:

```
reference        moved one cell    half brightness
0 0 0 0          0 0 0 0           0    0    0    0
0 1 1 0          0 0 1 1           0   0.5  0.5   0
0 1 1 0          0 0 1 1           0   0.5  0.5   0
0 0 0 0          0 0 0 0           0    0    0    0

                 mae = 0.25        mae = 0.125
```

The displaced candidate scores twice as badly as the damped one. Mean squared error, on
these same fields, makes it four times. Both prefer the damped candidate; they disagree
about by how much, and below one cell that disagreement grows into a factor of tens.

What this metric ignores is the arrangement of the errors: the same total error
concentrated at a sharp front and scattered as noise across the domain are the same
number.

## Reading the output

The value runs from zero upwards with no upper limit, in the field's own units, so a
density field and a vorticity field produce numbers that cannot be compared with each
other. Lower is better, and zero means the two fields are identical cell for cell. Because
it is linear rather than squared, the number is directly readable as a typical error size:
an MAE of 0.01 means the average cell is off by about 0.01 of whatever the field measures.

What counts as good depends entirely on the variance of the field being predicted, which
is why the suite reports damage — the value rescaled so that zero is the reference and one
is what two statistically similar but positionally unrelated fields score.

Comparisons across models on the same field, dataset and analysis grid are meaningful and
are the intended use. Comparisons across fields need normalising because of the units.
Comparisons across resolutions are invalid as they stand: the value is a mean over cells,
so refining the grid reweights the small scales even when nothing about the prediction has
changed. Compare on a common analysis grid, which is what this suite remaps onto before
measuring.

## Limitations

The linear response is a double-edged property. It makes MAE far more sensitive than MSE
to sub-cell displacement, which is useful when position matters, but it also means a
single catastrophically wrong region is not flagged any more urgently than the same total
error spread thinly everywhere. A model that is excellent across the domain and badly
wrong in one small area can score better than one that is mediocre throughout, and MAE
will not tell you which situation you are in.

It is also blind to position in the same way as every metric that compares fields cell by
cell, so a shock with exactly the right shape and strength sitting one cell over is
penalised twice: once where it should be and is not, once where it is and should not be.
And the absolute value is not differentiable at zero error, which matters if it is used as
a training loss rather than a diagnostic.

## Results

<!-- GENERATED run: written by `python -m fmeval.cards evidence mae --results results/comparison_1787115827`, do not edit -->

Measured on `kinet_re5e4`, frames 2000 to 10000 (161 frames of developed flow), on the 256 analysis grid, seed 20260807, at commit `85ddd3788061` (working tree dirty). Run `comparison_1787115827`.

Every number in this section comes from that one run. Regenerate with `python -m fmeval.cards evidence <name> --results results/comparison_1787115827`.

<!-- END GENERATED run -->

Each subsection links to the degradations that subsection reports. What those degradations
do, and what their strength numbers mean, is documented on their own pages.

### Smoothing

[gaussian_blur](../../degradations/gaussian_blur/card.md) ·
[box_blur](../../degradations/box_blur/card.md) ·
[median_blur](../../degradations/median_blur/card.md)

<!-- GENERATED results_smoothing: written by `python -m fmeval.cards evidence mae --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `box_blur` | density | 4 | 1 | 1 | 0.963 |
| `box_blur` | velocity | 4 | 1 | 1 | 1 |
| `box_blur` | vorticity | 4 | 1 | 1 | 0.815 |
| `gaussian_blur` | density | 4 | 1 | 1 | 0.976 |
| `gaussian_blur` | velocity | 4 | 1 | 1 | 1 |
| `gaussian_blur` | vorticity | 4 | 1 | 1 | 0.933 |
| `median_blur` | density | 3 | 1 | 1 | 0.973 |
| `median_blur` | velocity | 3 | 1 | 1 | 0.977 |
| `median_blur` | vorticity | 3 | 1 | 1 | 0.887 |

<!-- END GENERATED results_smoothing -->

### Spectral filtering

[lowpass_ideal](../../degradations/lowpass_ideal/card.md) ·
[lowpass_butterworth](../../degradations/lowpass_butterworth/card.md) ·
[highpass_ideal](../../degradations/highpass_ideal/card.md) ·
[highpass_butterworth](../../degradations/highpass_butterworth/card.md)

<!-- GENERATED results_spectral: written by `python -m fmeval.cards evidence mae --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `highpass_butterworth` | density | 4 | 0.8 | 0 | 0.308 |
| `highpass_butterworth` | velocity | 3 | 1 | 1 | 0.864 |
| `highpass_butterworth` | vorticity | 4 | 0.8 | 0.298 | 0.323 |
| `highpass_ideal` | density | 3 | 0.5 | 0 | 0.192 |
| `highpass_ideal` | velocity | 2 | 1 | 1 | 0.874 |
| `highpass_ideal` | vorticity | 4 | 0.8 | 0 | 0.324 |
| `lowpass_butterworth` | density | 4 | 1 | 1 | 0.843 |
| `lowpass_butterworth` | velocity | 3 | 1 | 1 | 1 |
| `lowpass_butterworth` | vorticity | 4 | 1 | 1 | 0.719 |
| `lowpass_ideal` | density | 3 | 1 | 1 | 0.948 |
| `lowpass_ideal` | velocity | 2 | 1 | 1 | 0.995 |
| `lowpass_ideal` | vorticity | 4 | 1 | 1 | 0.657 |

<!-- END GENERATED results_spectral -->

### Displacement

[translate_x](../../degradations/translate/card.md) ·
[translate_subpixel](../../degradations/translate_subpixel/card.md)

<!-- GENERATED results_geometric: written by `python -m fmeval.cards evidence mae --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `translate_subpixel` | density | 6 | 1 | 1 | 0.961 |
| `translate_subpixel` | velocity | 6 | 1 | 1 | 0.96 |
| `translate_subpixel` | vorticity | 6 | 1 | 1 | 0.862 |
| `translate_x` | density | 5 | 1 | 1 | 0.959 |
| `translate_x` | velocity | 5 | 1 | 1 | 0.96 |
| `translate_x` | vorticity | 5 | 1 | 1 | 0.795 |

<!-- END GENERATED results_geometric -->

The response is linear in the displacement, as Equation (2) gives: on vorticity the damage
ratios per doubling below one cell are 2.00, 1.98 and 1.93 against the 2 implied by that
scaling. Against MSE over the same shifts, MAE assigns 47 times the damage at an eighth of
a cell and 6.2 times at one cell, and its damage at an eighth of a cell is 0.023 against
MSE's 0.00048. Of the cell-by-cell baselines, MAE is the one that notices sub-cell
displacement.

### Resolution loss

[coarsen](../../degradations/coarsen/card.md)

<!-- GENERATED results_resolution: written by `python -m fmeval.cards evidence mae --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `coarsen` | density | 4 | 1 | 1 | 0.962 |
| `coarsen` | velocity | 4 | 1 | 1 | 1 |
| `coarsen` | vorticity | 4 | 1 | 1 | 0.942 |

<!-- END GENERATED results_resolution -->

### Noise

[additive_noise](../../degradations/additive_noise/card.md)

<!-- GENERATED results_stochastic: written by `python -m fmeval.cards evidence mae --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `additive_noise` | density | 4 | 1 | 1 | 1 |
| `additive_noise` | velocity | 4 | 1 | 1 | 1 |
| `additive_noise` | vorticity | 4 | 1 | 1 | 1 |

<!-- END GENERATED results_stochastic -->

### Trap tests

[gaussian_impostor](../../degradations/gaussian_impostor/card.md) ·
[uncorrelated](../../degradations/random_large_translation/card.md)

<!-- GENERATED results_canaries: written by `python -m fmeval.cards evidence mae --results results/comparison_1787115827`, do not edit -->

| field | impostor damage | nearest severity level | unrelated-field value |
|---|---|---|---|
| density | 1.36 | `highpass_ideal=3.03099` | 0.00521 |
| velocity | 0.757 | `highpass_ideal=4.02293` | 0.0593 |
| vorticity | 1.41 | `translate_x=16` | 0.00186 |

Damage of 1 is what an unrelated field scores, so the impostor column says how close to useless this metric considers a field with the reference's spectrum and random phases. The nearest severity level names the ordinary degradation whose damage the impostor most resembles, which is the more legible statement of the same thing.

<!-- END GENERATED results_canaries -->

### Compared with the other metrics

<!-- GENERATED results_summary: written by `python -m fmeval.cards evidence mae --results results/comparison_1787115827`, do not edit -->

| against | rank correlation across the ladder |
|---|---|
| `rmse` | 0.987 |
| `mse` | 0.987 |
| `nrmse` | 0.977 |
| `enstrophy` | -0.0874 |
| `kinetic_energy` | -0.208 |

Computed on the median value at each (axis, severity level), over every axis and field in the run, with the reference excluded. Two metrics correlating near 1 order the degradations alike; they may still weight them very differently, so this says they are redundant for ranking models rather than interchangeable as training losses.

<!-- END GENERATED results_summary -->

MAE and MSE correlate at 0.987 across every degradation, above the 0.95 redundancy
threshold, and MAE against NRMSE at 0.977 — they order the degradations almost identically
while differing by 47 times in sub-cell displacement damage. For ranking models the
cell-by-cell baselines are duplicates of one another; as training losses they are not.

One place MAE differs in kind rather than degree: it assigns the phase-scrambled fake
prediction a damage of 1.41 on vorticity, above the 1.0 an unrelated field scores. Reach
for MAE over MSE when small displacements are what you need to see, and when you do not
want the score dominated by the worst cell.

## References

\bibliography
