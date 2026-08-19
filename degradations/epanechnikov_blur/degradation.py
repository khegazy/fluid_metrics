"""The `epanechnikov_blur` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np

from .._shared.kernels import _convolve_spatial, _radial_kernel
from ..registry import degradation


@degradation(
    family="smoothing",
    severity_name="radius",
    severity_units="cells",
    severity_direction="increasing",
    calibration="scale",
)
def epanechnikov_blur(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Epanechnikov kernel, 3/4 (1 - u^2): the MSE-optimal smoothing kernel."""
    if severity < 1:
        return x
    kernel = _radial_kernel(severity, ctx.grid.n_spatial, "epanechnikov")
    return _convolve_spatial(x, kernel)
