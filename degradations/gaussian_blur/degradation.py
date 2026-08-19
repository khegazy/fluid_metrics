"""The `gaussian_blur` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter

from ..registry import degradation


@degradation(
    family="smoothing",
    severity_name="sigma",
    severity_units="cells",
    severity_direction="increasing",
    calibration="scale",
)
def gaussian_blur(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Isotropic Gaussian kernel smoothing.

    Monotone in wavenumber -- it attenuates every scale and amplifies none, which makes it
    the well-behaved reference against which the other kernels are read.
    """
    if severity <= 0:
        return x
    return gaussian_filter(x, sigma=severity, mode="wrap", axes=ctx.spatial_axes)
