---
name: kinetic_energy
kind: metric
---

## Definition

For a velocity field $u$ on the analysis grid with $C$ components and $N$ cells,

$$
E(u) = \frac{1}{2N} \sum_{i=1}^{N} \sum_{c=1}^{C} u_{c,i}^{2} \tag{1}
$$

Components are summed before the average over cells. This is the *specific* kinetic
energy, per unit mass: the density-weighted form is the conserved quantity, but at Mach
0.1 with density varying under 4% the two differ negligibly, and Equation (1) needs only
one field.

Like enstrophy, it takes one field and returns one number, and is evaluated on the
reference and on every degraded variant so the drift can be read downstream.

### Boundary handling

None. The operation is local to each cell, so no neighbourhood is ever consulted and no
boundary condition can enter.

## Performance

<!-- GENERATED performance: written by `python -m fmeval.cards evidence kinetic_energy --results results/comparison_1787115827`, do not edit -->

| test | field | axes | rank correlation | weakest separation | first detected |
|---|---|---|---|---|---|
| geometric | velocity | 2 | — to — | 0.497 | level — |
| resolution | velocity | 1 | -1 to -1 | 0 | level — |
| smoothing | velocity | 3 | -1 to -1 | 0 | level — |
| spectral | velocity | 4 | -1 to -1 | 0 | level — |
| stochastic | velocity | 1 | 1 to 1 | 0.511 | level — |
| canary: phase-randomised impostor | velocity | 1 | — | — | damage — |

Rank correlation is the per-frame Spearman correlation of the metric with severity, reported as the range over the axes in that family; 1 means every severity ordered correctly in every frame. Weakest separation is the smallest Mann-Whitney overlap between neighbouring severities. First detected is the lowest severity level at which the metric departs from clean by a tenth of the distance to an unrelated field. Damage is on that same scale: 0 is the reference and 1 is an unrelated field.

This table reports what was measured and grades none of it. What the numbers mean for this metric is in the subsections below, beside the test that produced each.

<!-- END GENERATED performance -->

## Intuition

Kinetic energy measures how fast the flow is moving, by squaring the local speed
everywhere and averaging. Squaring means direction is discarded — a flow and its exact
reverse carry the same energy — and that the fastest regions dominate the total. Unlike
enstrophy, most of this quantity sits in the largest structures of the flow rather than
the smallest.

That difference is what makes the pair useful together. A surrogate that has smoothed away
the fine structure loses enstrophy while its kinetic energy barely moves, because the
energy was never in the fine structure to begin with. A surrogate whose overall amplitude
has drifted shows up here.

On a four-by-four grid with a uniform unit flow in one component:

```
velocity (u)     velocity (v)     kinetic energy
1 1 1 1          0 0 0 0
1 1 1 1          0 0 0 0          0.5
1 1 1 1          0 0 0 0
1 1 1 1          0 0 0 0
```

Half of unit speed squared gives 0.5. Concentrating the same energy into half the domain,
at a speed of the square root of two, gives 0.5 as well.

That is what it ignores: how the energy is distributed. Any two flows with the same mean
squared speed are identical to this quantity, however differently they are arranged.

## Reading the output

The value runs from zero upwards with no upper limit, in the square of the velocity units.
There is no direction in which it is better: like enstrophy, it is a property of a flow
rather than an error, read by comparing the prediction against the reference on the same
frame.

Because energy sits at the large scales, this quantity is far more robust to grid
coarsening than enstrophy is, and a departure from the reference is more likely to mean a
genuine amplitude error than a resolution artefact. In freely decaying turbulence the
reference value falls along the trajectory, so a comparison must be made frame by frame
against the reference at that time and never against a single number for the run.

Comparing absolute values across datasets is not meaningful; comparing each prediction's
drift from its own reference is.

## Limitations

The degeneracy is total: energy says nothing about where the motion is or what shape it
takes, so a prediction can match it exactly while getting the flow entirely wrong. Matching
here is not evidence of a good prediction, only the absence of one particular kind of bad
one.

It is also the least sensitive diagnostic in the panel to the failures this project cares
about. Smoothing, which destroys the small scales a surrogate is most likely to lose,
removes very little energy, so a flat kinetic energy across the smoothing degradations
should be read as this metric being the wrong instrument rather than as the prediction
being sound.

Finally, this is specific energy, not the conserved density-weighted quantity. At higher
Mach number, or in a flow with real density contrast, the two separate and the conserved
form is the one to reach for.

## Results

<!-- GENERATED run: written by `python -m fmeval.cards evidence kinetic_energy --results results/comparison_1787115827`, do not edit -->

Measured on `kinet_re5e4`, frames 2000 to 10000 (161 frames of developed flow), on the 256 analysis grid, seed 20260807, at commit `85ddd3788061` (working tree dirty). Run `comparison_1787115827`.

Every number in this section comes from that one run. Regenerate with `python -m fmeval.cards evidence <name> --results results/comparison_1787115827`.

<!-- END GENERATED run -->

Each subsection links to the degradations that subsection reports. What those degradations
do, and what their strength numbers mean, is documented on their own pages. A single-field
diagnostic is evaluated on the reference and on every degraded variant alike, so what is
read here is the drift away from the reference value rather than an error.

### Smoothing

[gaussian_blur](../../degradations/gaussian_blur/card.md) ·
[box_blur](../../degradations/box_blur/card.md) ·
[median_blur](../../degradations/median_blur/card.md)

<!-- GENERATED results_smoothing: written by `python -m fmeval.cards evidence kinetic_energy --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `box_blur` | velocity | 4 | -1 | 0 | 0 |
| `gaussian_blur` | velocity | 4 | -1 | 0 | 0 |
| `median_blur` | velocity | 3 | -1 | 0 | 0.000502 |

<!-- END GENERATED results_smoothing -->

### Spectral filtering

[lowpass_ideal](../../degradations/lowpass_ideal/card.md) ·
[lowpass_butterworth](../../degradations/lowpass_butterworth/card.md) ·
[highpass_ideal](../../degradations/highpass_ideal/card.md) ·
[highpass_butterworth](../../degradations/highpass_butterworth/card.md)

<!-- GENERATED results_spectral: written by `python -m fmeval.cards evidence kinetic_energy --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `highpass_butterworth` | velocity | 3 | -1 | 0 | 0 |
| `highpass_ideal` | velocity | 2 | -1 | 0 | 0 |
| `lowpass_butterworth` | velocity | 3 | -1 | 0 | 0 |
| `lowpass_ideal` | velocity | 2 | -1 | 0 | 0 |

<!-- END GENERATED results_spectral -->

### Displacement

[translate_x](../../degradations/translate/card.md) ·
[translate_subpixel](../../degradations/translate_subpixel/card.md)

<!-- GENERATED results_geometric: written by `python -m fmeval.cards evidence kinetic_energy --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `translate_subpixel` | velocity | 6 | — | 0 | 0.497 |
| `translate_x` | velocity | 5 | — | 0 | 0.5 |

<!-- END GENERATED results_geometric -->

A translation moves the field without changing any of its values, so a quantity built from
those values alone cannot see it at all. This degradation is expected to be flat, and a
measurement showing otherwise would indicate the translation is not conserving what it
should — which is one of the things a reference-free diagnostic is useful for.

### Resolution loss

[coarsen](../../degradations/coarsen/card.md)

<!-- GENERATED results_resolution: written by `python -m fmeval.cards evidence kinetic_energy --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `coarsen` | velocity | 4 | -1 | 0 | 0 |

<!-- END GENERATED results_resolution -->

### Noise

[additive_noise](../../degradations/additive_noise/card.md)

<!-- GENERATED results_stochastic: written by `python -m fmeval.cards evidence kinetic_energy --results results/comparison_1787115827`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
|---|---|---|---|---|---|
| `additive_noise` | velocity | 4 | 1 | 0.969 | 0.511 |

<!-- END GENERATED results_stochastic -->

### Trap tests

[gaussian_impostor](../../degradations/gaussian_impostor/card.md) ·
[uncorrelated](../../degradations/random_large_translation/card.md)

<!-- GENERATED results_canaries: written by `python -m fmeval.cards evidence kinetic_energy --results results/comparison_1787115827`, do not edit -->

| field | impostor damage | nearest severity level | unrelated-field value |
|---|---|---|---|
| velocity | — | `` | 0.00157 |

Damage of 1 is what an unrelated field scores, so the impostor column says how close to useless this metric considers a field with the reference's spectrum and random phases. The nearest severity level names the ordinary degradation whose damage the impostor most resembles, which is the more legible statement of the same thing.

<!-- END GENERATED results_canaries -->

### Compared with the other metrics

<!-- GENERATED results_summary: written by `python -m fmeval.cards evidence kinetic_energy --results results/comparison_1787115827`, do not edit -->

| against | rank correlation across the ladder |
|---|---|
| `enstrophy` | 0.862 |
| `mae` | -0.208 |
| `mse` | -0.23 |
| `rmse` | -0.23 |
| `nrmse` | -0.29 |

Computed on the median value at each (axis, severity level), over every axis and field in the run, with the reference excluded. Two metrics correlating near 1 order the degradations alike; they may still weight them very differently, so this says they are redundant for ranking models rather than interchangeable as training losses.

<!-- END GENERATED results_summary -->

## References

\bibliography
