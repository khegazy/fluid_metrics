"""The `lowpass_butterworth` degradation.

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
    defaults={"order": 4},
)
def lowpass_butterworth(x: np.ndarray, severity: float, *, ctx, order: int = 4) -> np.ndarray:
    """Smooth low-pass, ``1 / (1 + (k/k_c)^(2n))``. No ringing: the ideal filter's control."""
    k = _wavenumber_magnitude(ctx.grid.shape)
    with np.errstate(divide="ignore", over="ignore"):
        transfer = 1.0 / (1.0 + (k / max(severity, 1e-12)) ** (2 * order))
    return _apply_filter(x, transfer)
