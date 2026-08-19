"""The `translate` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np

from .._shared.geometry import _axes_for
from ..registry import degradation


@degradation(
    family="geometric",
    severity_name="distance",
    severity_units="cells",
    severity_direction="increasing",
    defaults={"axis": "x"},
)
def translate(x: np.ndarray, severity: float, *, ctx, axis: str = "x") -> np.ndarray:
    """Whole-cell periodic translation.

    Exact and cheap, but quantised: on a periodic grid ``translate(x, N) == x``, and the
    smallest nonzero displacement is one cell.
    """
    shift = int(round(severity))
    if shift == 0:
        return x
    axes = _axes_for(axis, ctx)
    return np.roll(x, shift=(shift,) * len(axes), axis=axes)
