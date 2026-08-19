"""The `highpass_ideal` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np

from .._shared.filters import _apply_filter, _wavenumber_magnitude
from ..registry import degradation


@degradation(
    family="spectral",
    severity_name="energy removed",
    severity_units="fraction",
    severity_direction="increasing",
    calibration="energy_below",
)
def highpass_ideal(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Sharp high-pass: zero every mode with |k| < cutoff, keeping the spatial mean.

    Removes the energy-containing large scales. Not a realistic surrogate failure, but a
    direct test of whether a metric registers large-scale structure at all.

    **The k=0 mode is preserved deliberately.** Deleting it removes the spatial mean, which
    for a field like density (1.0 with fluctuations of 2e-4) is a change four orders of
    magnitude larger than anything the cutoff controls. Measured before this was fixed:
    every severity level gave an identical damage of 2.7e7 relative to the unrelated-field level, so
    the axis carried no ordering at all and its rank correlation collapsed to 0.10. Keeping
    the mean makes the operator measure what it is named for -- removal of large-scale
    structure -- and restores a monotone ladder on every field.
    """
    k = _wavenumber_magnitude(ctx.grid.shape)
    return _apply_filter(x, (k >= severity).astype(float), keep_mean=True)
