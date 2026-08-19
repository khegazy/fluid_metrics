---
name: mse
kind: metric
---

## Definition

For fields $f$ (reference) and $g$ (candidate) sampled on the same analysis grid, with $C$
channels and $N$ cells per channel,

$$
\mathrm{MSE}(f, g) = \frac{1}{CN} \sum_{c=1}^{C} \sum_{i=1}^{N}
\bigl( f_{c,i} - g_{c,i} \bigr)^2 \tag{1}
$$

For a vector field the channels are pooled rather than reduced separately. The analysis
grid is uniform, so cells carry equal weight; on a non-uniform grid Equation (1) would
need cell volumes and would no longer be a plain mean.

The pointwise map that this repository stores alongside the scalar is the summand,

$$
m_i = \sum_{c=1}^{C} \bigl( f_{c,i} - g_{c,i} \bigr)^2 ,
\qquad
\mathrm{MSE} = \frac{1}{C} \, \langle m \rangle \tag{2}
$$

The declared reduction is the mean divided by the channel count, and a contract test
checks that reducing the map reproduces the scalar.

For a displacement $\delta$ small compared with the scale of variation, expanding
$f(x + \delta) - f(x) \simeq \delta\, \partial_x f$ in Equation (1) gives the
scaling that governs everything this metric does with shifted features:

$$
\mathrm{MSE} \simeq \delta^{2} \bigl\langle (\partial_x f)^2 \bigr\rangle ,
\qquad
\mathrm{MAE} \simeq \delta \bigl\langle |\partial_x f| \bigr\rangle \tag{3}
$$

### Boundary handling

None. The operation is local to each cell, so no neighbourhood is ever consulted and no
boundary condition can enter.

## Performance

<!-- GENERATED performance: written by `python -m fmeval.cards evidence mse --results results/comparison_1787115827`, do not edit -->

| test | field | axes | rank correlation | weakest separation | first detected |
|---|---|---|---|---|---|
| geometric | density | 2 | 1 to 1 | 0.959 | level 5 |
| geometric | velocity | 2 | 1 to 1 | 0.984 | level — |
| geometric | vorticity | 2 | 1 to 1 | 0.754 | level 3 |
| resolution | density | 1 | 1 to 1 | 0.96 | level — |
| resolution | velocity | 1 | 1 to 1 | 1 | level — |
| resolution | vorticity | 1 | 1 to 1 | 0.741 | level 3 |
| smoothing | density | 3 | 1 to 1 | 0.955 | level 4 |
| smoothing | velocity | 3 | 1 to 1 | 0.986 | level — |
| smoothing | vorticity | 3 | 1 to 1 | 0.69 | level 4 |
| spectral | density | 4 | 1 to 1 | 0.698 | level 2 |
| spectral | velocity | 4 | 1 to 1 | 0.993 | level 3 |
| spectral | vorticity | 4 | 1 to 1 | 0.62 | level 1 |
| stochastic | density | 1 | 1 to 1 | 1 | level 4 |
| stochastic | velocity | 1 | 1 to 1 | 1 | level — |
| stochastic | vorticity | 1 | 1 to 1 | 1 | level 4 |
| canary: phase-randomised impostor | density | 1 | — | — | damage 1.23 |
| canary: phase-randomised impostor | velocity | 1 | — | — | damage 0.661 |
| canary: phase-randomised impostor | vorticity | 1 | — | — | damage 0.902 |

Rank correlation is the per-frame Spearman correlation of the metric with severity, reported as the range over the axes in that family; 1 means every severity ordered correctly in every frame. Weakest separation is the smallest Mann-Whitney overlap between neighbouring severities. First detected is the lowest severity level at which the metric departs from clean by a tenth of the distance to an unrelated field. Damage is on that same scale: 0 is the reference and 1 is an unrelated field.

This table reports what was measured and grades none of it. What the numbers mean for this metric is in the subsections below, beside the test that produced each.

<!-- END GENERATED performance -->

## Intuition

Mean squared error compares two fields one cell at a time: subtract, square, average.
Squaring keeps errors of opposite sign from cancelling and makes the largest local errors
dominate the total. Nothing in the calculation ever looks at more than one cell, so the
metric carries no notion of shape or position — it sees a bag of per-cell differences,
not a picture.

That locality produces its characteristic failure. A feature with the right shape and
strength but slightly displaced is wrong twice — once in the cells it left, once in the
cells it entered — while a feature in the right place with reduced amplitude is wrong
only once, and only by the amount reduced. On a four-by-four grid, with a candidate that
moved the square one cell and another that halved its brightness:

```
reference        moved one cell    half brightness
0 0 0 0          0 0 0 0           0    0    0    0
0 1 1 0          0 0 1 1           0   0.5  0.5   0
0 1 1 0          0 0 1 1           0   0.5  0.5   0
0 0 0 0          0 0 0 0           0    0    0    0

                 mse = 0.25        mse = 0.0625
```

The candidate that preserved the feature and only moved it scores four times worse. This
is the double penalty, and it is why a pointwise norm misjudges sharp features that are
nearly in the right place.

What it ignores is the arrangement of the errors: one error concentrated at a sharp front
and the same total error scattered as noise across the domain are the same number.

## Reading the output

The value runs from zero upwards with no upper limit, in the square of the field's units,
so a density field and a vorticity field produce numbers that cannot be compared with each
other. Lower is better, and zero means the two fields are identical cell for cell.

There is no value that counts as good in the abstract. What counts as good depends
entirely on the variance of the field being predicted: an error of 0.01 is excellent for a
field whose fluctuations are of order one and catastrophic for one whose fluctuations are
of order 0.001. That is why the suite reports damage, which rescales the value so that
zero is the reference and one is what two statistically similar but positionally unrelated
fields score, and why NRMSE exists as a normalised sibling.

Comparisons across models on the same field, the same dataset and the same analysis grid
are meaningful and are the intended use. Comparisons across fields are meaningless without
normalising, because of the units. Comparisons across resolutions are invalid as they
stand: the value is a mean over cells, so refining the grid changes the weight given to
small scales even when nothing about the prediction has changed. Compare on a common
analysis grid, which is what this suite remaps onto before measuring.

## Limitations

The concrete situation to recognise is a model that reproduces the structure of a flow
well but places it slightly wrong. Two candidates, one that predicts a shock of the right
strength one cell from its true position and one that smears the same shock over four
cells while keeping it centred, can receive similar mean squared errors even though a
person looking at the two fields would not hesitate to prefer the first. Ranking such
models by MSE therefore selects for smoothness. This is the mechanism behind the blurry
outputs that regression losses are known to produce, and it is visible in the results
here: the metric saturates slowly on displacement axes while responding immediately to
blurring.

Two further cautions. The value is not comparable across grid resolutions, because it is
a mean over cells, so a run whose analysis grid differs is not comparable at all. And
because the differences are squared, a single badly wrong cell can dominate the whole
field; this is an advantage when outliers are what matters and a liability when they are
an artefact of the reader or the remap.

## Results

<!-- GENERATED run: written by `python -m fmeval.cards evidence mse --results results/comparison_1787115827`, do not edit -->

Measured on `kinet_re5e4`, frames 2000 to 10000 (161 frames of developed flow), on the 256 analysis grid, seed 20260807, at commit `85ddd3788061` (working tree dirty). Run `comparison_1787115827`.

Every number in this section comes from that one run. Regenerate with `python -m fmeval.cards evidence <name> --results results/comparison_1787115827`.

<!-- END GENERATED run -->

Each subsection links to the degradations it reports; what those degradations do, and what
their severity numbers mean, is documented in their own bundles.

### Smoothing

[gaussian_blur](../../degradations/gaussian_blur/card.md) ·
[box_blur](../../degradations/box_blur/card.md) ·
[median_blur](../../degradations/median_blur/card.md)

<!-- GENERATED results_smoothing: written by `python -m fmeval.cards evidence mse --results results/comparison_1787115827`, do not edit -->

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

<!-- GENERATED results_spectral: written by `python -m fmeval.cards evidence mse --results results/comparison_1787115827`, do not edit -->

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

<!-- GENERATED results_geometric: written by `python -m fmeval.cards evidence mse --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `translate_subpixel` | density | 6 | 1 | 1 | 0.964 |
| `translate_subpixel` | velocity | 6 | 1 | 1 | 0.984 |
| `translate_subpixel` | vorticity | 6 | 1 | 1 | 0.838 |
| `translate_x` | density | 5 | 1 | 1 | 0.959 |
| `translate_x` | velocity | 5 | 1 | 1 | 0.984 |
| `translate_x` | vorticity | 5 | 1 | 1 | 0.754 |

<!-- END GENERATED results_geometric -->

The response is quadratic in the displacement, as Equation (3) gives: on vorticity the
damage ratios per doubling below one cell are 3.98, 3.94 and 3.75 against the 4 implied by
that scaling, falling to 3.18 and 2.10 above a cell as the expansion stops holding. MAE is
linear over the same shifts, so it assigns 47 times the damage at an eighth of a cell and
6.2 times at one cell. MSE therefore reads as tolerant of small displacements and severe
about moderate ones, and the double penalty has no single onset.

### Resolution loss

[coarsen](../../degradations/coarsen/card.md)

<!-- GENERATED results_resolution: written by `python -m fmeval.cards evidence mse --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `coarsen` | density | 4 | 1 | 1 | 0.96 |
| `coarsen` | velocity | 4 | 1 | 1 | 1 |
| `coarsen` | vorticity | 4 | 1 | 1 | 0.741 |

<!-- END GENERATED results_resolution -->

### Noise

[additive_noise](../../degradations/additive_noise/card.md)

<!-- GENERATED results_stochastic: written by `python -m fmeval.cards evidence mse --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `additive_noise` | density | 4 | 1 | 1 | 1 |
| `additive_noise` | velocity | 4 | 1 | 1 | 1 |
| `additive_noise` | vorticity | 4 | 1 | 1 | 1 |

<!-- END GENERATED results_stochastic -->

### Canaries

[gaussian_impostor](../../degradations/gaussian_impostor/card.md) ·
[uncorrelated](../../degradations/random_large_translation/card.md)

<!-- GENERATED results_canaries: written by `python -m fmeval.cards evidence mse --results results/comparison_1787115827`, do not edit -->

| field | impostor damage | nearest severity level | unrelated-field value |
|---|---|---|---|
| density | 1.23 | `lowpass_ideal=1.4029` | 6.56e-05 |
| velocity | 0.661 | `highpass_ideal=4.02293` | 0.00477 |
| vorticity | 0.902 | `translate_x=16` | 1.45e-05 |

Damage of 1 is what an unrelated field scores, so the impostor column says how close to useless this metric considers a field with the reference's spectrum and random phases. The nearest severity level names the ordinary degradation whose damage the impostor most resembles, which is the more legible statement of the same thing.

<!-- END GENERATED results_canaries -->

MSE rejects the phase-randomised impostor firmly: 0.90 damage on vorticity, 0.66 on
velocity, and 1.23 on density, where a damage above 1 means the impostor is scored worse
than a field with no relation to the reference at all. The canary is aimed at metrics
depending only on the amplitude spectrum, so it does not catch this family, and a panel in
which every metric rejects it is not evidence of a well-guarded panel.

### Across the ladder

<!-- GENERATED results_summary: written by `python -m fmeval.cards evidence mse --results results/comparison_1787115827`, do not edit -->

| against | rank correlation across the ladder |
|---|---|
| `rmse` | 1 |
| `mae` | 0.987 |
| `nrmse` | 0.979 |
| `enstrophy` | -0.108 |
| `kinetic_energy` | -0.23 |

Computed on the median value at each (axis, severity level), over every axis and field in the run, with the reference excluded. Two metrics correlating near 1 order the degradations alike; they may still weight them very differently, so this says they are redundant for ranking models rather than interchangeable as training losses.

<!-- END GENERATED results_summary -->

MSE and RMSE correlate at exactly 1: the square root is monotone, so no ranking can ever
separate them. Against the other baselines MSE sits at 0.987 with MAE and 0.979 with
NRMSE, above the 0.95 redundancy threshold, yet MAE assigns 47 times the damage at an
eighth of a cell. They order damage alike without weighting it alike, so for ranking
models they are duplicates and as training losses they are not. Reach for MSE when the
errors that matter are errors of amplitude, not of position.

## References

\bibliography
