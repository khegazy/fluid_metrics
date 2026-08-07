"""Resolution loss: coarsen and upsample back to the reference grid.

Distinct from the IN-2 analysis grid, which puts *both* fields on a coarse grid and
compares there. Here the field is coarsened and returned to the fine grid, so the damage
is measured against an undegraded reference at full resolution. Same block-average kernel
(:func:`fmeval.remap.block_average`), different question: this asks "how much does losing
resolution hurt?", the analysis grid asks "at what resolution are we willing to judge?".

There is exactly one coarsening implementation in the codebase, and it lives in
``fmeval.remap``.
"""

from __future__ import annotations

import numpy as np

from fmeval.remap import block_average
from fmeval.remap import subsample as _subsample_kernel

from .registry import degradation


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
