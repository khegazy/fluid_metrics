---
name: lowpass_ideal
kind: degradation
---

## Definition

The field is transformed, multiplied by a transfer function, and transformed back:

$$
\hat{g}(k) = H(|k|)\, \hat{f}(k), \qquad H(|k|) = 1 \text{ for } |k| \le k_c, \quad 0 \text{ otherwise} \tag{1}
$$

The cutoff $k_c$ is not configured directly. The severity states what fraction of the
field's energy should be removed, and the cutoff that achieves it is found from a spectrum
measured from the data, per field.

The wavenumber magnitude $|k|$ is the single definition shared with the severity
calibration, in ``fmeval.wavenumbers``. That sharing is not incidental: the filters and
the calibration once used two different definitions -- a continuous magnitude against
binned shells -- which put the diagonal modes on opposite sides of the same cutoff, and a
low-pass asked to remove 30% of the energy on density removed 99.997% of it, with every
intermediate number looking plausible.

### Boundary handling

Periodic by construction. The discrete Fourier transform assumes a periodic domain,
which this one is, so the filter wraps exactly and no windowing or padding is applied. On
a non-periodic field the transform would impose a spurious discontinuity at the edge and
the filter would ring against it.

## Intuition

This stands in for a surrogate that has lost its fine structure -- the same failure the
smoothing kernels imitate, but committed outright rather than gradually. A blur attenuates
the small scales; an ideal low-pass deletes them and leaves everything else exactly as it
was.

Both belong in the ladder because they differ in a way a metric can be blind to. A
Gaussian removes a little energy from every scale; this removes all the energy above one
wavenumber and none below it. A metric that reports the same damage for both at matched
energy loss is measuring the quantity removed rather than the manner of its removal.

In a picture the result is distinctive: features keep their positions and their broad
shapes but acquire ringing -- faint ripples beside every sharp edge, which are the Gibbs
oscillations a hard spectral cut always produces.

```
before (16x16, a bright 4x4 block)     after (low-pass removing 30% of energy)
max value       1.000                  max value       0.062
spatial mean    0.0625                 spatial mean    0.0625
```

The mean is untouched and the peak is almost gone: the block was built almost entirely
from the small scales the filter removed.

What it leaves untouched is the spatial mean: the
k = 0 mode is far below any cutoff this axis uses.

## Severity scale

The severity is the **fraction of spectral energy removed**, not a wavenumber. The
ladder asks for 5%, 15%, 30% and 45%, and the cutoff delivering each is resolved per field
from a spectrum measured over five evenly spaced frames.

This indirection is what makes the axis comparable between fields whose spectra differ by
orders of magnitude, and the realised removal now agrees with the request to within a few
percent wherever the spectrum can resolve it.

## Limitations

A sharp filter cannot resolve four distinct levels on every field, and on density it
cannot resolve them at all. 69% of that field's fluctuation energy sits in the four
diagonal modes at $|k| = \sqrt{2}$ and only 3 parts in 100000 in the axis modes at
$|k| = 1$, so the available cutoffs are few and far apart: a request for any fraction
between those two lands on the same cutoff, and the intermediate levels collapse onto one
another. Levels that collapse are detected and excluded rather than counted as agreement,
but the axis carries fewer usable levels there than the configured four.

The Butterworth variant exists precisely because it can resolve levels this one cannot.

The ringing is also a genuine artefact rather than a property of the failure being
imitated: no real surrogate produces Gibbs oscillations at every edge, so part of the
damage measured here is damage from an artefact.

## Exemplars

### The panel

{{ include _generated/exemplars.md }}

The radial spectrum row is the point of this panel. The cutoff appears as a cliff --
the curve follows the grey reference exactly and then drops to nothing at $k_c$, with the
cliff moving to lower wavenumber as the severity rises. That abruptness, against the
Gaussian panel's smooth departure, is the difference between the two ways of losing small
scales.

In the field row, look for ringing beside sharp features rather than for softening. In the
difference row the error is oscillatory and spread along edges rather than concentrated on
them.

## References

\bibliography
