"""The `spread_inflate` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np

from .._ensemble_ops import scale_spread
from ..registry import degradation


@degradation(
    family="ensemble",
    severity_name="excess dispersion",
    severity_units="fraction of the calibrated spread",
    severity_direction="increasing",
    ensemble=True,
)
def spread_inflate(members: np.ndarray, severity: float) -> np.ndarray:
    """Widen the ensemble about its own mean: the overdispersed, hedging forecast.

    Severity is the *excess* dispersion, so zero is a no-op and one doubles the spread.
    The ensemble mean is untouched, so this axis moves calibration without moving
    accuracy: any metric built on the ensemble mean alone is blind to it by
    construction, and a calibration metric should see it immediately.
    """
    if severity == 0:
        return members
    return scale_spread(members, 1.0 + severity)
