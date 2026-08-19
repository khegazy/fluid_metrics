---
name: nrmse
kind: metric
---

## Definition

For fields $f$ (reference) and $g$ (candidate) on the same analysis grid, write
$\bar{f}$ for the spatial mean of the reference and $f' = f - \bar{f}$ for its
fluctuation. Then

$$
\mathrm{NRMSE}(f, g) = \frac{\mathrm{RMSE}(f, g)}
{\sqrt{\langle f'^2 \rangle}} \tag{1}
$$

where the average runs over channels and cells. The denominator is the root-mean-square
*fluctuation* of the reference, not its raw root-mean-square.

That choice is not cosmetic. The kinet weakly compressible density field is
$1.0 \pm 1.8 \times 10^{-4}$, so its raw RMS is essentially one; dividing by that would
leave the value indistinguishable from RMSE and would hide four orders of magnitude of
relative error, making density and velocity incomparable on the same axis. Removing the
mean first is what puts them on one scale.

The reference alone sets the denominator, so Equation (1) is not symmetric: exchanging the
two fields changes the value. Where the reference is spatially uniform there is no
fluctuation scale to divide by, and the metric returns NaN rather than an exception or an
infinity.

### Boundary handling

None. The operation is local to each cell, and the spatial mean is taken over the whole
field, so no neighbourhood and no boundary condition enter.

## Performance

<!-- GENERATED performance: written by `python -m fmeval.cards evidence nrmse --results results/comparison_1787115827`, do not edit -->

| test | field | axes | rank correlation | weakest separation | first detected |
|---|---|---|---|---|---|
| geometric | density | 2 | 1 to 1 | 1 | level 3 |
| geometric | velocity | 2 | 1 to 1 | 0.984 | level 4 |
| geometric | vorticity | 2 | 1 to 1 | 0.81 | level 1 |
| resolution | density | 1 | 1 to 1 | 1 | level 4 |
| resolution | velocity | 1 | 1 to 1 | 1 | level — |
| resolution | vorticity | 1 | 1 to 1 | 0.886 | level 1 |
| smoothing | density | 3 | 1 to 1 | 0.999 | level 3 |
| smoothing | velocity | 3 | 1 to 1 | 0.986 | level 3 |
| smoothing | vorticity | 3 | 1 to 1 | 0.756 | level 2 |
| spectral | density | 4 | 1 to 1 | 0.954 | level 1 |
| spectral | velocity | 4 | 1 to 1 | 0.998 | level 1 |
| spectral | vorticity | 4 | 1 to 1 | 0.793 | level 1 |
| stochastic | density | 1 | 1 to 1 | 1 | level 4 |
| stochastic | velocity | 1 | 1 to 1 | 1 | level 4 |
| stochastic | vorticity | 1 | 1 to 1 | 1 | level 4 |
| canary: phase-randomised impostor | density | 1 | — | — | damage 1.09 |
| canary: phase-randomised impostor | velocity | 1 | — | — | damage 0.813 |
| canary: phase-randomised impostor | vorticity | 1 | — | — | damage 0.945 |

Rank correlation is the per-frame Spearman correlation of the metric with severity, reported as the range over the axes in that family; 1 means every severity ordered correctly in every frame. Weakest separation is the smallest Mann-Whitney overlap between neighbouring severities. First detected is the lowest severity level at which the metric departs from clean by a tenth of the distance to an unrelated field. Damage is on that same scale: 0 is the reference and 1 is an unrelated field.

This table reports what was measured and grades none of it. What the numbers mean for this metric is in the subsections below, beside the test that produced each.

<!-- END GENERATED performance -->

## Intuition

Normalised root mean squared error is the root mean squared error expressed as a fraction
of how much the reference field actually varies. An error of one unit means something
quite different in a field that swings by a thousand and in one that swings by two, and
dividing by the size of the reference's own variation is what makes those two situations
produce the same number.

The variation used is the fluctuation about the spatial mean, not the raw size of the
field. This matters more than it sounds. A density field sitting at one with ripples of
a ten-thousandth would, if divided by its raw size, report a tiny error no matter how
badly the ripples were predicted, because the constant background would swamp everything.
Subtracting the mean first means the ripples are compared against the ripples.

Here is the whole point on a four-by-four grid. The same displaced feature is scored
twice: once as it stands, and once with both fields multiplied by a ten-thousandth, as a
density fluctuation riding on a background of one might be.

```
                          rmse      nrmse
as it stands              0.5       1.155
both fields x 0.0001      0.00005   1.155
```

The unnormalised score falls by four orders of magnitude and says nothing about whether
the prediction got worse. The normalised one does not move, because the error and the
reference's variation shrank together.

The consequence is that this is the one pointwise control whose value can be read across
fields: a value of 0.1 means the error is a tenth of the field's variation, whether the
field is density, velocity or vorticity. It also means the reference and the candidate are
not interchangeable, since only the reference sets the scale.

What it ignores is the same thing every pointwise norm ignores: where the errors sit.

## Reading the output

The value runs from zero upwards with no upper limit and is dimensionless. Lower is
better, and zero means the fields are identical. One is a useful landmark rather than a
bound: it means the error is as large as the reference's own fluctuation, which is roughly
what predicting the mean everywhere would achieve.

Because it is dimensionless, this is the pointwise control that supports the comparison
the others cannot: across fields, and across datasets whose fields have different
magnitudes. Comparisons across models on one field are of course still valid.

Two cautions. It is asymmetric, so the reference must genuinely be the reference. And it
is undefined for a spatially uniform reference, where it returns NaN — a run reporting NaN
here is reporting that the field had no fluctuation to normalise against, not that
something failed.

## Limitations

The normalisation hides absolute magnitude, which is occasionally the thing you needed to
know. Two models with the same NRMSE on fields whose fluctuations differ by three orders
of magnitude have wildly different absolute errors, and if the downstream use is sensitive
to absolute error the number will not warn you.

The denominator is measured from the reference on each frame, so as the flow decays and
its fluctuation shrinks, the same absolute error produces a growing NRMSE. That is
usually the desired behaviour, but it means a rising NRMSE along a trajectory does not by
itself indicate a worsening prediction.

Being a positive rescaling of RMSE, it orders candidates on a single field exactly as MSE
and RMSE do, and inherits their blindness to position and their quadratic response to
sub-cell displacement.

## Results

<!-- GENERATED run: written by `python -m fmeval.cards evidence nrmse --results results/comparison_1787115827`, do not edit -->

Measured on `kinet_re5e4`, frames 2000 to 10000 (161 frames of developed flow), on the 256 analysis grid, seed 20260807, at commit `85ddd3788061` (working tree dirty). Run `comparison_1787115827`.

Every number in this section comes from that one run. Regenerate with `python -m fmeval.cards evidence <name> --results results/comparison_1787115827`.

<!-- END GENERATED run -->

Each subsection links to the degradations it reports; what those degradations do, and what
their severity numbers mean, is documented in their own bundles.

### Smoothing

[gaussian_blur](../../degradations/gaussian_blur/card.md) ·
[box_blur](../../degradations/box_blur/card.md) ·
[median_blur](../../degradations/median_blur/card.md)

<!-- GENERATED results_smoothing: written by `python -m fmeval.cards evidence nrmse --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `box_blur` | density | 4 | 1 | 1 | 0.999 |
| `box_blur` | velocity | 4 | 1 | 1 | 1 |
| `box_blur` | vorticity | 4 | 1 | 1 | 0.756 |
| `gaussian_blur` | density | 4 | 1 | 1 | 1 |
| `gaussian_blur` | velocity | 4 | 1 | 1 | 1 |
| `gaussian_blur` | vorticity | 4 | 1 | 1 | 0.857 |
| `median_blur` | density | 3 | 1 | 1 | 1 |
| `median_blur` | velocity | 3 | 1 | 1 | 0.986 |
| `median_blur` | vorticity | 3 | 1 | 1 | 0.912 |

<!-- END GENERATED results_smoothing -->

### Spectral filtering

[lowpass_ideal](../../degradations/lowpass_ideal/card.md) ·
[lowpass_butterworth](../../degradations/lowpass_butterworth/card.md) ·
[highpass_ideal](../../degradations/highpass_ideal/card.md) ·
[highpass_butterworth](../../degradations/highpass_butterworth/card.md)

<!-- GENERATED results_spectral: written by `python -m fmeval.cards evidence nrmse --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `highpass_butterworth` | density | 4 | 1 | 1 | 0.987 |
| `highpass_butterworth` | velocity | 3 | 1 | 1 | 1 |
| `highpass_butterworth` | vorticity | 4 | 1 | 1 | 0.925 |
| `highpass_ideal` | density | 3 | 1 | 1 | 0.996 |
| `highpass_ideal` | velocity | 2 | 1 | 1 | 1 |
| `highpass_ideal` | vorticity | 4 | 1 | 1 | 0.945 |
| `lowpass_butterworth` | density | 4 | 1 | 1 | 0.954 |
| `lowpass_butterworth` | velocity | 3 | 1 | 1 | 1 |
| `lowpass_butterworth` | vorticity | 4 | 1 | 1 | 0.793 |
| `lowpass_ideal` | density | 3 | 1 | 1 | 0.998 |
| `lowpass_ideal` | velocity | 2 | 1 | 1 | 0.998 |
| `lowpass_ideal` | vorticity | 4 | 1 | 1 | 0.815 |

<!-- END GENERATED results_spectral -->

### Displacement

[translate_x](../../degradations/translate/card.md) ·
[translate_subpixel](../../degradations/translate_subpixel/card.md)

<!-- GENERATED results_geometric: written by `python -m fmeval.cards evidence nrmse --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `translate_subpixel` | density | 6 | 1 | 1 | 1 |
| `translate_subpixel` | velocity | 6 | 1 | 1 | 0.984 |
| `translate_subpixel` | vorticity | 6 | 1 | 1 | 0.885 |
| `translate_x` | density | 5 | 1 | 1 | 1 |
| `translate_x` | velocity | 5 | 1 | 1 | 0.984 |
| `translate_x` | vorticity | 5 | 1 | 1 | 0.81 |

<!-- END GENERATED results_geometric -->


### Resolution loss

[coarsen](../../degradations/coarsen/card.md)

<!-- GENERATED results_resolution: written by `python -m fmeval.cards evidence nrmse --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `coarsen` | density | 4 | 1 | 1 | 1 |
| `coarsen` | velocity | 4 | 1 | 1 | 1 |
| `coarsen` | vorticity | 4 | 1 | 1 | 0.886 |

<!-- END GENERATED results_resolution -->

### Noise

[additive_noise](../../degradations/additive_noise/card.md)

<!-- GENERATED results_stochastic: written by `python -m fmeval.cards evidence nrmse --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `additive_noise` | density | 4 | 1 | 1 | 1 |
| `additive_noise` | velocity | 4 | 1 | 1 | 1 |
| `additive_noise` | vorticity | 4 | 1 | 1 | 1 |

<!-- END GENERATED results_stochastic -->

### Canaries

[gaussian_impostor](../../degradations/gaussian_impostor/card.md) ·
[uncorrelated](../../degradations/random_large_translation/card.md)

<!-- GENERATED results_canaries: written by `python -m fmeval.cards evidence nrmse --results results/comparison_1787115827`, do not edit -->

| field | impostor damage | nearest severity level | unrelated-field value |
|---|---|---|---|
| density | 1.09 | `lowpass_ideal=1.4029` | 1.28 |
| velocity | 0.813 | `highpass_ideal=4.02293` | 1.75 |
| vorticity | 0.945 | `translate_x=16` | 1.5 |

Damage of 1 is what an unrelated field scores, so the impostor column says how close to useless this metric considers a field with the reference's spectrum and random phases. The nearest severity level names the ordinary degradation whose damage the impostor most resembles, which is the more legible statement of the same thing.

<!-- END GENERATED results_canaries -->

### Across the ladder

<!-- GENERATED results_summary: written by `python -m fmeval.cards evidence nrmse --results results/comparison_1787115827`, do not edit -->

| against | rank correlation across the ladder |
|---|---|
| `mse` | 0.979 |
| `rmse` | 0.979 |
| `mae` | 0.977 |
| `enstrophy` | -0.162 |
| `kinetic_energy` | -0.29 |

Computed on the median value at each (axis, severity level), over every axis and field in the run, with the reference excluded. Two metrics correlating near 1 order the degradations alike; they may still weight them very differently, so this says they are redundant for ranking models rather than interchangeable as training losses.

<!-- END GENERATED results_summary -->

NRMSE correlates with MSE at 0.979 and with MAE at 0.977 across the full ladder, above the
0.95 redundancy threshold. Its distinct contribution is not a different ordering but a
comparable scale: it is the control that allows a density result and a vorticity result to
be read side by side.

## References

\bibliography
