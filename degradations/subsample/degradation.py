"""The `subsample` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np

from .._shared.grids import _subsample_kernel, _upsample
from ..registry import degradation


@degradation(
    family="resolution",
    severity_name="factor",
    severity_units="",
    severity_direction="increasing",
)
def subsample(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Point-sample every ``factor``-th cell, then expand back. The non-conservative control.

    Aliases small scales into large ones rather than removing them: measured on the real
    256^2 field at factor 8, this retains 102% of the variance where block averaging
    retains 73%. Pairing the two makes the aliasing visible as a metric response rather
    than a claim.
    """
    factor = int(round(severity))
    if factor <= 1:
        return x
    return _upsample(_subsample_kernel(x, factor), factor, x.shape[1:])
