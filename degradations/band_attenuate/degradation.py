"""The `band_attenuate` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np

from .._shared.filters import _apply_filter, _wavenumber_magnitude
from ..registry import degradation


@degradation(
    family="spectral",
    severity_name="retained fraction",
    severity_units="",
    severity_direction="decreasing",  # retaining LESS is worse
    defaults={"k_lo": 16.0, "k_hi": 64.0},
)
def band_attenuate(
    x: np.ndarray, severity: float, *, ctx, k_lo: float = 16.0, k_hi: float = 64.0
) -> np.ndarray:
    """Scale the amplitude of one wavenumber band by ``severity``, leaving the rest alone.

    The direct experimental test of the NM-3 / BD-3 organising principle: damage a single
    scale band and a genuinely scale-selective metric should respond only when the band it
    targets is the one damaged. A metric whose response is the same wherever the damage
    sits is measuring "badness in general".
    """
    k = _wavenumber_magnitude(ctx.grid.shape)
    transfer = np.ones_like(k)
    transfer[(k >= k_lo) & (k <= k_hi)] = severity
    return _apply_filter(x, transfer)
