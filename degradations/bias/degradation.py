"""The `bias` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np

from ..registry import degradation


@degradation(
    family="pointwise",
    severity_name="offset",
    severity_units="fraction of fluctuation rms",
    severity_direction="increasing",
)
def bias(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Add a uniform offset scaled to the reference fluctuation RMS.

    Invisible to any metric built on fluctuations or gradients, which is the point: it
    separates metrics that track the absolute level from those that do not.
    """
    if severity == 0:
        return x
    return x + severity * ctx.fluctuation_rms
