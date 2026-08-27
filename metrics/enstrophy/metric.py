"""Enstrophy: mean squared vorticity, a reference-free physics diagnostic.

A single-field metric: it characterises one field rather than comparing two. The pipeline
evaluates it on the reference and on every degraded variant, and ``fmeval.analysis``
derives the drift from that, so the comparison happens downstream rather than here.
"""

from __future__ import annotations

import numpy as np

from ..registry import metric


@metric(
    name="enstrophy",
    arity="single",
    fields=("vorticity",),
    returns="scalar",
    differentiable=True,
    cost="cheap",
    higher_is_better=False,   # no direction of its own: the drift from the reference
                              # is what is read
    symmetric=False,
    units="field^2",
)
def enstrophy(x: np.ndarray) -> float:
    """Mean enstrophy, one half the mean squared vorticity magnitude.

    Parameters
    ----------
    x
        Vorticity on the analysis grid, shape ``(C, *spatial)``. One component in 2D,
        three in 3D; components are summed before averaging over cells.

    Returns
    -------
    float
        ``0.5 * <|omega|^2>``, in the square of the vorticity units.
    """
    return float(0.5 * (x**2).sum(axis=0).mean())
