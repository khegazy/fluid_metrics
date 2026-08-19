"""The `box_blur` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter

from .._shared.kernels import _odd_width
from ..registry import degradation


@degradation(
    family="smoothing",
    severity_name="width",
    severity_units="cells",
    severity_direction="increasing",
    calibration="scale",
)
def box_blur(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Square top-hat (moving average) smoothing.

    Its transfer function is a sinc, so it has sidelobes: some wavenumbers are amplified
    rather than attenuated, and the kernel is square rather than isotropic. Both are
    reasons a metric might distinguish it from a Gaussian of matched width.
    """
    width = _odd_width(severity)
    if width <= 1:
        return x
    size = [1] * x.ndim
    for axis in ctx.spatial_axes:
        size[axis] = width
    return uniform_filter(x, size=size, mode="wrap")
