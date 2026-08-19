---
name: band_attenuate
kind: degradation
---

## Definition

The field is transformed, multiplied by a transfer function, and transformed back:

$$
\hat{g}(k) = H(|k|)\, \hat{f}(k), \qquad H(|k|) = r \text{ for } k_{lo} \le |k| \le k_{hi}, \quad 1 \text{ otherwise} \tag{1}
$$

where $r$ is the retained fraction and the band edges $k_{lo}$ and $k_{hi}$ are fixed
options rather than part of the severity, defaulting to 16 and 64.

Note the direction: this operator declares ``severity_direction="decreasing"``, the only
one in the suite that does, because a *smaller* retained fraction is a *larger*
degradation. The ladder sorts its levels accordingly, so a configured list running from
0.8 down to 0.0 produces levels of increasing damage.

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

This stands in for a surrogate that gets one range of scales wrong while handling both
larger and smaller ones correctly -- a model with a defect at a particular scale rather
than a general loss of resolution.

That is a more specific failure than the low-pass and high-pass axes imitate, and it is
the one that most directly tests whether a metric localises error in wavenumber. A metric
that only reports total energy lost will score a band attenuation the same as a low-pass
that removed the same amount, even though the two fields differ in where the loss sits.

In a picture, structures of one particular size fade while both larger and smaller ones
remain, which is a strange and distinctive appearance.

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

The severity is the **retained** fraction within the band: 0.8 keeps most of the band
and 0.0 removes it entirely. This is the one axis where a larger severity number means a
milder degradation, which the declared decreasing direction handles.

The band edges are absolute wavenumbers, fixed at 16 and 64 by default, and are **not**
calibrated per field. That is a real limitation of this axis: the same band means
different things on fields whose spectra differ.

The axis is disabled in the default ladder.

## Limitations

The uncalibrated band edges are the main weakness. Every other spectral axis resolves
its cutoff per field against a measured spectrum; this one uses fixed wavenumbers, so the
band may sit in the energetic range on one field and in the dissipation range on another,
and the damage is not comparable between them. That is why it is disabled by default.

The decreasing direction is also a trap for anyone reading the raw configuration: a list
that looks like it descends is in fact ascending in damage. The declared direction handles
it, and a contract test verifies the declaration against measurement, but the raw numbers
are misleading to the eye.

## Exemplars

### The panel

{{ include _generated/exemplars.md }}

The field row is the one to study, and it rewards patience: neither the largest nor
the smallest structures change, and only an intermediate band fades. That is unlike every
other panel in this gallery.

The radial spectrum row shows the mechanism plainly as a notch -- the curve follows the
reference, dips within the band, and returns. Check that the notch edges sit at the same
wavenumbers in every column, since only its depth should change with severity.

## References

\bibliography
