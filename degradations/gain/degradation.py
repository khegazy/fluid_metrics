"""The `gain` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np

from ..registry import degradation


@degradation(
    family="pointwise",
    severity_name="gain error",
    severity_units="relative",
    severity_direction="increasing",
)
def gain(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Scale the fluctuation by ``1 + severity``, leaving the spatial mean intact.

    Pure amplitude error with zero position error: every feature stays exactly where it
    was and every gradient keeps its sign.
    """
    if severity == 0:
        return x
    spatial = tuple(range(1, x.ndim))
    mean = x.mean(axis=spatial, keepdims=True)
    return mean + (1.0 + severity) * (x - mean)
