"""The `lowpass_ideal` degradation.

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
    calibration="energy_above",
)
def lowpass_ideal(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Sharp low-pass: zero every mode above the cutoff, removing the small scales.

    Rings near sharp features (Gibbs). Compare against `lowpass_butterworth` to separate
    "lost small scales" from "gained ringing".

    ``severity`` reaches this function already resolved to a cutoff wavenumber by the ladder,
    from the requested fraction of energy to remove.
    """
    k = _wavenumber_magnitude(ctx.grid.shape)
    return _apply_filter(x, (k <= severity).astype(float))
