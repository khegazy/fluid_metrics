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

The sum runs over all channels and all cells with equal weight, so for a vector field the
components are pooled rather than reduced separately. The grid is uniform and the domain
doubly periodic, so no boundary term and no cell-volume weighting appears; on a
non-uniform grid Equation (1) would need cell volumes and would no longer be a plain
mean.

There is no boundary handling to state because the operation is local to each cell. This
is exactly why the metric is cheap, and also why it can say nothing about position: no
neighbourhood ever enters the calculation.

The pointwise map that this repository stores alongside the scalar is the summand,

$$
m_i = \sum_{c=1}^{C} \bigl( f_{c,i} - g_{c,i} \bigr)^2 ,
\qquad
\mathrm{MSE} = \frac{1}{C} \, \langle m \rangle \tag{2}
$$

where the average is over cells. The declared reduction is the mean divided by the channel
count, and a contract test checks that reducing the map reproduces the scalar.

For a displacement $\delta$ small compared with the scale of variation, expanding
$f(x + \delta) - f(x) \simeq \delta\, \partial_x f$ in Equation (1) gives the
scaling that governs everything this metric does with shifted features:

$$
\mathrm{MSE} \simeq \delta^{2} \bigl\langle (\partial_x f)^2 \bigr\rangle ,
\qquad
\mathrm{MAE} \simeq \delta \bigl\langle |\partial_x f| \bigr\rangle \tag{3}
$$

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

## Evidence

{{ include _generated/evidence.md }}

## Assessment

Measurements on 256-squared vorticity at Reynolds 5e4, over 21 frames of developed flow,
confirm the quadratic scaling of Equation (3): the damage ratios
per doubling of sub-cell displacement are 3.99, 3.95 and 3.82, against the 4 implied by a
quadratic response, and MAE gives 2.00, 1.98 and 1.93 against the 2 implied by a
linear one. The
practical consequence is large and easy to miss. At an eighth of a cell MAE assigns 55
times the damage MSE does, and at one full cell 6.5 times. If what you need is a pointwise
metric that notices sub-cell displacement, MAE is strictly the better choice, and the
quadratic suppression is why MSE reads as tolerant of small shifts while being severe
about moderate ones. The double penalty has no single onset; where it begins depends on
the order of the norm.

The phase-randomised impostor does not catch this family: MSE assigns it
0.80 damage on vorticity and 0.51 on velocity, which is firm rejection. That canary is
aimed at metrics that depend only on the amplitude spectrum, and a report in which every
implemented metric rejects the impostor should not be read as reassuring until such a
metric is actually in the panel.

Against the controls, the three pointwise baselines correlate at 0.995 (MAE against MSE),
0.970 (MSE against NRMSE) and 0.968 (MAE against NRMSE) across the full ladder, all above
the 0.95 redundancy threshold, so they order the degradations almost identically. They
still differ by a factor of 55 in displacement damage. High rank correlation means two
metrics *order* damage the same way, not that they *weight* it the same. For selecting
models by ranking, these three are duplicates; as training losses they are not.

Reach for MSE when the errors you care about are errors of amplitude — a model that
damps, that adds noise, that loses the small scales — and when you want a cheap,
differentiable quantity with a long history behind its interpretation. Do not reach for it
alone when position is what matters.

## References

\bibliography
