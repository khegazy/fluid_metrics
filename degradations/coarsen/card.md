---
name: coarsen
kind: degradation
---

## Definition

The field is averaged over non-overlapping blocks of $m \times m$ cells and the
result is expanded back to the original grid by nearest-neighbour repetition:

$$
\bar{f}_{J} = \frac{1}{m^{d}} \sum_{i \in J} f_i, \qquad
g_i = \bar{f}_{J(i)} \tag{1}
$$

where $J(i)$ is the block containing cell $i$. The block average is the same operator the
analysis grid uses (``fmeval.remap.block_average``); there is exactly one coarsening
implementation in the codebase.

The expansion is nearest-neighbour rather than interpolated on purpose: it reintroduces no
information and adds no smoothing of its own, so what is measured is resolution loss alone
rather than resolution loss convolved with an interpolation kernel.

This is distinct from the IN-2 analysis grid, which puts *both* fields on a coarse grid
and compares there. Here only the candidate is coarsened and the comparison happens at full
resolution, which asks how much losing resolution hurts rather than at what resolution we
are willing to judge.

### Boundary handling

None needed. The blocks tile the domain exactly when the factor divides the grid
size, and no cell outside the block is ever consulted, so no boundary condition enters.
A factor that does not divide the grid is rejected rather than handled.

## Intuition

This stands in for a surrogate run at lower resolution than the truth it is compared
against, or one whose effective resolution is coarser than the grid it writes on. It is
the most literal form of losing the small scales, and unlike a smooth kernel it removes
them with a hard edge.

The visible result is blockiness: flat square plateaus, each the average of what used to
be a neighbourhood, with sharp steps between them. On the four-by-four example a factor of
two averages every two-by-two block, and since the bright square straddles all four blocks
equally the field becomes uniform:

```
before                 after (factor 2)
0 0 0 0                0.25 0.25 0.25 0.25
0 1 1 0                0.25 0.25 0.25 0.25
0 1 1 0                0.25 0.25 0.25 0.25
0 0 0 0                0.25 0.25 0.25 0.25
```

The feature vanishes entirely into a uniform field of its own mean value. On a real field
the effect is less total but the mechanism is the same.

What it leaves untouched is the spatial mean, exactly, and the large scales: structures
much wider than a block come through nearly unchanged.

## Severity scale

The severity is the coarsening factor -- the number of cells per block along each
axis -- and is **absolute** rather than calibrated. A factor of four means four on density
and on vorticity alike, because the quantity of interest is resolution in cells rather
than resolution relative to the flow's own scale.

The ladder runs at 2, 4, 8 and 16, each a doubling. The factor must divide the analysis
grid size, which is what bounds the ladder from above: on a small analysis grid the larger
factors are not runnable and are dropped before the run rather than silently producing
something else.

## Limitations

Coarsening and expanding is not the same as simulating at lower resolution, and the
difference matters. A genuinely coarse simulation evolves its own dynamics and develops
different large scales; this takes a correct fine field and degrades it, so the large
scales remain exactly right. As an imitation of a low-resolution surrogate it is
therefore optimistic.

The nearest-neighbour expansion introduces a half-block displacement of feature centroids
that is not present in the underlying block average, which contributes a small amount of
displacement damage on top of the resolution loss. That was preferred to an interpolating
expansion, which would have contributed smoothing instead, but it is not nothing.

A derived field must be recomputed after coarsening rather than block-averaged: the
average of a curl is not the curl of the average, and the difference reaches 5.6%, 18.3%
and 25.9% at factors of 2, 4 and 8.

## Exemplars

### The panel

{{ include _generated/exemplars.md }}

The field row shows the plateaus growing as the factor rises, and it is the clearest
of any panel in the gallery -- resolution loss is the one degradation the eye judges well.

The difference row shows error concentrated where the field varies fastest and near zero
in smooth regions, which is the same signature as a smoothing kernel. The radial spectrum
row is where the two separate: a block average imposes a hard cut with sidelobes rather
than a smooth roll-off, so the curve drops abruptly and then rings, where a Gaussian
descends smoothly. If a metric responds identically here and on the Gaussian axis at
matched damage, it is not seeing the difference between a soft and a hard loss of
scales.

## References

\bibliography
