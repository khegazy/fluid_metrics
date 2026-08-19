"""The `median_blur` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import median_filter

from .._shared.kernels import _odd_width
from ..registry import degradation


@degradation(
    family="smoothing",
    severity_name="width",
    severity_units="cells",
    severity_direction="increasing",
    calibration="scale",
)
def median_blur(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Median filter: nonlinear, and edge-preserving where a Gaussian smears.

    The interesting contrast for this project. A metric that scores median and Gaussian
    smoothing the same at matched width is not seeing the sharp structure that the
    shock-oriented metrics are supposed to target.
    """
    width = _odd_width(severity)
    if width <= 1:
        return x
    size = [1] * x.ndim
    for axis in ctx.spatial_axes:
        size[axis] = width
    return median_filter(x, size=size, mode="wrap")
