"""Mean absolute error: the pointwise L1 baseline.

One of the pointwise controls the position-tolerant metrics are read against. It shares
MSE's blindness to position and differs in how steeply it punishes what it does see: the
absolute value is linear in the error where the square is quadratic, which changes the
metric's behaviour on small displacements by a large factor.
"""

from __future__ import annotations

import numpy as np

from ..registry import metric, pointwise_map


@metric(
    name="mae",
    arity="pairwise",
    fields=("*",),
    returns="scalar",
    differentiable=True,      # everywhere except at zero error, where the subgradient is used
    cost="cheap",
    higher_is_better=False,
    symmetric=True,
    units="field",
    reduction="mean",
)
def mae(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Mean absolute error over all channels and cells.

    Parameters
    ----------
    reference
        Reference field on the analysis grid, shape ``(C, *spatial)``.
    candidate
        Candidate field, same shape.

    Returns
    -------
    float
        The mean of ``|reference - candidate|``, in the field's own units.
    """
    return float(np.abs(reference - candidate).mean())


@pointwise_map(of="mae")
def mae_map(reference: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    """Per-cell absolute error, summed over channels.

    Reduces to :func:`mae` by the declared ``mean`` reduction, divided by the channel
    count.
    """
    return np.abs(reference - candidate).sum(axis=0)
