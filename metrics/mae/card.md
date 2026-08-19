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

<!-- GENERATED performance: written by `python -m fmeval.cards evidence mae`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence mae`.

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

What it ignores is the arrangement of the errors: the same total error concentrated at a
sharp front and scattered as noise across the domain are the same number.

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

It is also blind to position in the same way as every pointwise norm, so a shock with
exactly the right shape and strength sitting one cell over is penalised twice: once where
it should be and is not, once where it is and should not be. And the absolute value is not
differentiable at zero error, which matters if it is used as a training loss rather than a
diagnostic.

## Results

<!-- GENERATED run: written by `python -m fmeval.cards evidence mae`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence mae`.

<!-- END GENERATED run -->

Each subsection links to the degradations it reports; what those degradations do, and what
their severity numbers mean, is documented in their own bundles.

### Smoothing

[gaussian_blur](../../degradations/gaussian_blur/card.md) ·
[box_blur](../../degradations/box_blur/card.md) ·
[median_blur](../../degradations/median_blur/card.md)

<!-- GENERATED results_smoothing: written by `python -m fmeval.cards evidence mae`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence mae`.

<!-- END GENERATED results_smoothing -->

### Spectral filtering

[lowpass_ideal](../../degradations/lowpass_ideal/card.md) ·
[lowpass_butterworth](../../degradations/lowpass_butterworth/card.md) ·
[highpass_ideal](../../degradations/highpass_ideal/card.md) ·
[highpass_butterworth](../../degradations/highpass_butterworth/card.md)

<!-- GENERATED results_spectral: written by `python -m fmeval.cards evidence mae`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence mae`.

<!-- END GENERATED results_spectral -->

### Displacement

[translate_x](../../degradations/translate/card.md) ·
[translate_subpixel](../../degradations/translate_subpixel/card.md)

<!-- GENERATED results_geometric: written by `python -m fmeval.cards evidence mae`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence mae`.

<!-- END GENERATED results_geometric -->

The response is linear in the displacement, as Equation (2) gives: the damage ratios per
doubling below one cell are 2.00, 1.98 and 1.93 against the 2 implied by that scaling.
Against MSE over the same shifts, MAE assigns 55 times the damage at an eighth of a cell
and 6.5 times at one cell. Of the pointwise controls it is the one that notices sub-cell
displacement.

### Resolution loss

[coarsen](../../degradations/coarsen/card.md)

<!-- GENERATED results_resolution: written by `python -m fmeval.cards evidence mae`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence mae`.

<!-- END GENERATED results_resolution -->

### Noise

[additive_noise](../../degradations/additive_noise/card.md)

<!-- GENERATED results_stochastic: written by `python -m fmeval.cards evidence mae`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence mae`.

<!-- END GENERATED results_stochastic -->

### Canaries

[gaussian_impostor](../../degradations/gaussian_impostor/card.md) ·
[uncorrelated](../../degradations/random_large_translation/card.md)

<!-- GENERATED results_canaries: written by `python -m fmeval.cards evidence mae`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence mae`.

<!-- END GENERATED results_canaries -->

### Across the ladder

<!-- GENERATED results_summary: written by `python -m fmeval.cards evidence mae`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence mae`.

<!-- END GENERATED results_summary -->

MAE and MSE correlate at 0.995 across the full ladder, above the 0.95 redundancy
threshold, and MAE against NRMSE at 0.968 — they order the degradations almost
identically while differing by 55 times in displacement damage. For ranking models the
pointwise controls are duplicates of one another; as training losses they are not. Reach
for MAE over MSE when small displacements are what you need to see, and when you do not
want the score dominated by the worst cell.

## References

\bibliography
