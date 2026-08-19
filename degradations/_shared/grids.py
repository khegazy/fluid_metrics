"""Grid coarsening and expansion, shared by the resolution operators."""

from __future__ import annotations

import numpy as np

from fmeval.remap import block_average
from fmeval.remap import subsample as _subsample_kernel

__all__ = ["_upsample", "block_average", "_subsample_kernel"]


def _upsample(x: np.ndarray, factor: int, shape: tuple[int, ...]) -> np.ndarray:
    """Nearest-neighbour expansion back to the original grid.

    Nearest rather than bilinear on purpose: it reintroduces no information and no new
    smoothing, so the damage measured is resolution loss alone rather than resolution loss
    convolved with an interpolation kernel.
    """
    out = x
    for axis in range(1, x.ndim):
        out = np.repeat(out, factor, axis=axis)
    return out
