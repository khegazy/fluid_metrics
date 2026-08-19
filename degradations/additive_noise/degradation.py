"""The `additive_noise` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np

from ..registry import degradation


@degradation(
    family="stochastic",
    severity_name="amplitude",
    severity_units="fraction of fluctuation rms",
    severity_direction="increasing",
    stochastic=True,
)
def additive_noise(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Gaussian noise scaled to a fraction of the reference fluctuation RMS."""
    if severity <= 0:
        return x
    return x + severity * ctx.fluctuation_rms * ctx.rng.standard_normal(x.shape)
