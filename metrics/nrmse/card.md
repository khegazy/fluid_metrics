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

{{ include _generated/performance.md }}

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

{{ include _generated/run.md }}

Each subsection links to the degradations it reports; what those degradations do, and what
their severity numbers mean, is documented in their own bundles.

### Smoothing

[gaussian_blur](../../degradations/gaussian_blur/card.md) ·
[box_blur](../../degradations/box_blur/card.md) ·
[median_blur](../../degradations/median_blur/card.md)

{{ include _generated/results_smoothing.md }}

### Spectral filtering

[lowpass_ideal](../../degradations/lowpass_ideal/card.md) ·
[lowpass_butterworth](../../degradations/lowpass_butterworth/card.md) ·
[highpass_ideal](../../degradations/highpass_ideal/card.md) ·
[highpass_butterworth](../../degradations/highpass_butterworth/card.md)

{{ include _generated/results_spectral.md }}

### Displacement

[translate_x](../../degradations/translate/card.md) ·
[translate_subpixel](../../degradations/translate_subpixel/card.md)

{{ include _generated/results_geometric.md }}


### Resolution loss

[coarsen](../../degradations/coarsen/card.md)

{{ include _generated/results_resolution.md }}

### Noise

[additive_noise](../../degradations/additive_noise/card.md)

{{ include _generated/results_stochastic.md }}

### Canaries

[gaussian_impostor](../../degradations/gaussian_impostor/card.md) ·
[uncorrelated](../../degradations/random_large_translation/card.md)

{{ include _generated/results_canaries.md }}

### Across the ladder

{{ include _generated/results_summary.md }}

NRMSE correlates with MSE at 0.970 and with MAE at 0.968 across the full ladder, above the
0.95 redundancy threshold. Its distinct contribution is not a different ordering but a
comparable scale: it is the control that allows a density result and a vorticity result to
be read side by side.

## References

\bibliography
