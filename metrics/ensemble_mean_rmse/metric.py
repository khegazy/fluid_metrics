"""RMSE of the ensemble mean: the deterministic control for the probabilistic family.

The number every ensemble study reports beside CRPS, and the one that says how good the
ensemble's single best guess is while saying nothing at all about its uncertainty. It
plays the role for probabilistic metrics that the pointwise family plays for the rest of
the suite: a candidate that cannot beat it is not earning the cost of an ensemble.

Reading it against CRPS is the point. CRPS falls when the ensemble is both accurate and
honestly dispersed; this falls only when the centre moves. A model that sharpens its
ensemble without moving the mean improves one and leaves the other exactly where it was,
and a test in this bundle pins that.
"""

from __future__ import annotations

import numpy as np

from .._ensemble import as_ensemble
from ..registry import metric
from ..rmse.metric import rmse


@metric(
    name="ensemble_mean_rmse",
    arity="ensemble",
    fields=("*",),
    returns="scalar",
    differentiable=True,
    cost="cheap",
    higher_is_better=False,
    symmetric=False,
    units="field",
    reduction="sqrt_mean",
)
def ensemble_mean_rmse(reference: np.ndarray, members: np.ndarray) -> float:
    """Root mean squared error of the ensemble mean against the reference.

    .. math::

        \\mathrm{RMSE}_{\\bar{x}} = \\sqrt{\\frac{1}{CN}\\sum_{c,i}
            \\Bigl( \\frac{1}{M}\\sum_{m} x_{m,c,i} - y_{c,i} \\Bigr)^2 }

    The ensemble is collapsed first and scored second; averaging the per-member errors
    instead would give a different and larger number, since the mean of the errors is not
    the error of the mean.

    Args:
        reference: Reference realization, shape ``(C, *spatial)``.
        members: Ensemble members, shape ``(N, C, *spatial)``.

    Returns:
        The score in the field's own units. Zero when the ensemble mean is exact.

    Raises:
        ValueError: If ``members`` does not carry a leading member axis, or is empty.
    """
    reference, members = as_ensemble(
        reference, members, min_members=1, what="ensemble_mean_rmse"
    )
    return rmse(reference, members.mean(axis=0))
