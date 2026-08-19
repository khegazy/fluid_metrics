"""The `coarsen` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np

from fmeval.remap import block_average
from .._shared.grids import _upsample
from ..registry import degradation


@degradation(
    family="resolution",
    severity_name="factor",
    severity_units="",
    severity_direction="increasing",
)
def coarsen(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Conservative block average by ``factor``, then expand back to the fine grid.

    Block-mean rather than point-sampling, per IN-2's "compare cell averages".
    """
    factor = int(round(severity))
    if factor <= 1:
        return x
    return _upsample(block_average(x, factor), factor, x.shape[1:])
