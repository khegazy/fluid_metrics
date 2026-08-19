"""Root mean squared error: mean squared error carried back to the field's units.

Defined in terms of :func:`metrics.mse.metric.mse` rather than repeating the sum, so the
two cannot drift apart. Importing across bundles is the intended pattern: the ``@metric``
decorator returns the function unwrapped, and the import system registers each bundle
exactly once.
"""

from __future__ import annotations

import numpy as np

from ..mse.metric import mse
from ..registry import metric, pointwise_map


@metric(
    name="rmse",
    arity="pairwise",
    fields=("*",),
    returns="scalar",
    differentiable=True,
    cost="cheap",
    higher_is_better=False,
    symmetric=True,
    units="field",
    reduction="sqrt_mean",
)
def rmse(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Root mean squared error; the same units as the field.

    Parameters
    ----------
    reference
        Reference field on the analysis grid, shape ``(C, *spatial)``.
    candidate
        Candidate field, same shape.

    Returns
    -------
    float
        The square root of the mean squared error.
    """
    return float(np.sqrt(mse(reference, candidate)))


@pointwise_map(of="rmse")
def rmse_map(reference: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    """Per-cell *squared* error, summed over channels.

    Note the declared reduction is ``sqrt_mean``, not ``mean``: this map does not average
    to the metric value. That mismatch is exactly why the reduction is declared on the
    decorator rather than assumed from the map.
    """
    return ((reference - candidate) ** 2).sum(axis=0)
