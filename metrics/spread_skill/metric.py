"""Spread-to-skill ratio: is the ensemble as uncertain as it ought to be?

A forecast that is confident and wrong is worse than a forecast that is uncertain and
wrong, because the first one tells you to act on it. This ratio is the standard check for
that failure: the typical disagreement among the members, divided by the typical error of
their consensus. A ratio near one says the ensemble's own uncertainty is an honest
estimate of its error. Below one it is overconfident; above one it hedges.

**The number is reported raw, calibrated at one.** Most metrics in this repository are
errors, best at zero and monotone in damage. This one is not: it is wrong in both
directions, and its distance from one is what counts. That is a property of the
quantity, not an inconvenience to be transformed away, so the metric reports the ratio
the literature reports and declares ``target=1.0``; the analysis layer orients its
ordering statistics by distance from that target.

**The estimator is the one Fortin et al. (2014) argue for**, and it is not the obvious
one. See the docstring below, and the test that pins it.
"""

from __future__ import annotations

import numpy as np

from .._ensemble import as_ensemble
from ..registry import metric


@metric(
    name="spread_skill",
    arity="ensemble",
    fields=("*",),
    returns="scalar",
    differentiable=False,     # a ratio of two square roots; not a loss
    cost="cheap",
    higher_is_better=False,   # neither, in fact: see target
    symmetric=False,
    units="dimensionless",
    reduction="mean",
    target=1.0,
    measures="calibration",
)
def spread_skill(reference: np.ndarray, members: np.ndarray) -> float:
    """Ratio of RMS ensemble spread to the RMSE of the ensemble mean.

    The spread is the square root of the *mean variance*,

    .. math::

        s = \\sqrt{ \\frac{1}{CN} \\sum_{c,i} \\sigma^2_{c,i} },
        \\qquad
        \\sigma^2_{c,i} = \\frac{1}{M-1}\\sum_m (x_{m,c,i} - \\bar{x}_{c,i})^2,

    **not** the mean of the per-cell spreads. Fortin et al. (2014, J. Hydrometeor.
    15:1708) show the latter is biased low -- it is an average of square roots where the
    unbiased quantity is the square root of an average, and Jensen's inequality gives the
    sign -- and that in an operational setting the mistake changed the verdict from
    "underdispersed" to "excellent agreement". The two forms differ by a factor of
    sqrt(2) on the worked example in this bundle's tests.

    The skill is the RMSE of the ensemble mean over the same cells. Under exchangeability
    the expected squared error of the mean of :math:`M` members exceeds the ensemble
    variance by :math:`(M+1)/M`, so the raw ratio of a perfectly calibrated ensemble is
    :math:`\\sqrt{M/(M+1)}` rather than one. That factor is divided out here, which is
    what makes a 4-member run and a 50-member run directly comparable.

    Args:
        reference: Reference realization, shape ``(C, *spatial)``.
        members: Ensemble members, shape ``(N, C, *spatial)``. At least two.

    Returns:
        The ratio. One is calibrated, below one is overconfident, above one hedges.
        Zero when the ensemble has collapsed to a point; infinite when the ensemble mean
        is exact but the members still disagree.

    Raises:
        ValueError: If ``members`` lacks a leading member axis or has fewer than two
            members, which would leave the sample variance undefined.
    """
    reference, members = as_ensemble(
        reference, members, min_members=2, what="spread_skill"
    )
    n_members = members.shape[0]

    # Fortin et al. (2014): sqrt of the MEAN variance, never the mean of the spreads.
    variance = members.var(axis=0, ddof=1)
    spread = float(np.sqrt(variance.mean()))

    error = members.mean(axis=0) - reference
    skill = float(np.sqrt((error**2).mean()))

    # Finite-ensemble correction, so a calibrated ensemble reads one at any size.
    spread *= np.sqrt((n_members + 1) / n_members)

    if skill == 0.0:
        # An exact ensemble mean. Zero spread with it is the degenerate perfect case;
        # non-zero spread is unbounded overdispersion, and inf says so honestly rather
        # than a large finite number that would look like a measurement.
        return 0.0 if spread == 0.0 else float("inf")
    return spread / skill
