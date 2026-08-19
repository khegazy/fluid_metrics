"""The `identity` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np

from ..registry import degradation


@degradation(
    name="identity",
    family="identity",
    severity_name="n/a",
    severity_units="",
    severity_direction="increasing",
)
def identity(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """No-op: level 0 of every ladder. Pairwise error metrics must return exactly 0 here."""
    return x
