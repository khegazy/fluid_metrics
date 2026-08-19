"""The `multiplicative_noise` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np

from ..registry import degradation


@degradation(
    family="stochastic",
    severity_name="amplitude",
    severity_units="relative",
    severity_direction="increasing",
    stochastic=True,
)
def multiplicative_noise(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Multiply by ``1 + severity * N(0, 1)``: error proportional to the local value."""
    if severity <= 0:
        return x
    return x * (1.0 + severity * ctx.rng.standard_normal(x.shape))
