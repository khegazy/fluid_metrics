"""The `spread_deflate` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np

from .._ensemble_ops import scale_spread
from ..registry import degradation


@degradation(
    family="ensemble",
    severity_name="lost dispersion",
    severity_units="fraction of the calibrated spread",
    severity_direction="increasing",
    ensemble=True,
)
def spread_deflate(members: np.ndarray, severity: float) -> np.ndarray:
    """Narrow the ensemble about its own mean: the overconfident forecast.

    Severity is the fraction of dispersion removed, so zero is a no-op and one collapses
    the ensemble onto its mean -- a prediction claiming certainty it has not earned.
    This is the more dangerous half of the calibration axis in practice: an
    overconfident ensemble tells a user to act on it.

    Kept as a separate operator from ``spread_inflate`` rather than folded into one
    signed severity, because the ladder sorts a single operator's severities along one
    monotone axis of increasing damage. Dispersion error is not monotone in a signed
    scale factor -- it is least damaging in the middle -- so the two directions are two
    axes, each mildest at zero.
    """
    if severity == 0:
        return members
    if not 0.0 <= severity <= 1.0:
        raise ValueError(
            f"spread_deflate severity is a fraction of the spread to remove, so it must "
            f"lie in [0, 1]; got {severity}"
        )
    return scale_spread(members, 1.0 - severity)
