"""Continuous ranked probability score, in its fair ensemble form.

The score the probabilistic forecasting community verifies against, and the natural
generalization of mean absolute error to a prediction that is a distribution rather than a
number. It is *strictly proper*: the forecaster minimizes it only by reporting their true
belief, so it cannot be gamed by hedging the spread in either direction.

Two properties make it the right first probabilistic metric here. It collapses to mean
absolute error when the ensemble has one member, which puts it on the same scale as the
existing pointwise controls and makes the comparison against them exact rather than
merely qualitative. And it rewards sharpness subject to calibration in a single number,
where the spread-to-skill ratio and the rank histogram each see only one half of that.

The estimator is the *fair* one (Ferro 2014). The obvious plug-in form -- replace both
expectations with sample means over the ensemble -- is biased low for finite N, and its
bias depends on the ensemble size, so a model run with more members would appear better
than the same model run with fewer. The fair form removes that by excluding self-pairs
from the second term. On the worked example in the card the two differ by a factor of
three, which is not a subtlety.
"""

from __future__ import annotations

import numpy as np

from ..registry import metric


@metric(
    name="crps",
    arity="ensemble",
    fields=("*",),
    returns="scalar",
    differentiable=True,      # piecewise linear; subgradient at ties, as for mae
    cost="cheap",
    higher_is_better=False,
    symmetric=False,          # reference and ensemble are different kinds of object
    units="field",
    reduction="mean",
)
def crps(reference: np.ndarray, members: np.ndarray) -> float:
    """Fair ensemble CRPS, averaged over channels and cells.

    The kernel (energy) representation of the score is

    .. math::

        \\mathrm{CRPS}(F, y) = \\mathbb{E}|X - y|
                             - \\tfrac{1}{2}\\mathbb{E}|X - X'|,

    for independent :math:`X, X' \\sim F` (Gneiting & Raftery 2007, JASA 102(477):359,
    Section 4.2). Estimating both expectations from an ensemble of size :math:`N` while
    keeping the estimator unbiased gives the fair form used here,

    .. math::

        \\widehat{\\mathrm{CRPS}} = \\frac{1}{N}\\sum_i |x_i - y|
            - \\frac{1}{2N(N-1)}\\sum_i\\sum_j |x_i - x_j|,

    whose second denominator is :math:`2N(N-1)` rather than the plug-in :math:`2N^2`
    (Ferro 2014, QJRMS 140:1917). At :math:`N = 1` the second term is defined to be zero
    and the score is exactly :math:`|x_1 - y|`.

    Args:
        reference: Reference realization on the analysis grid, shape ``(C, *spatial)``.
        members: Ensemble members, shape ``(N, C, *spatial)``, member axis leading.

    Returns:
        The score in the field's own units. Zero when every member equals the reference;
        larger is worse.

    Raises:
        ValueError: If ``members`` does not carry a leading member axis over an array
            shaped like ``reference``, or if the ensemble is empty.
    """
    reference = np.asarray(reference, dtype=np.float64)
    members = np.asarray(members, dtype=np.float64)

    if members.ndim != reference.ndim + 1 or members.shape[1:] != reference.shape:
        raise ValueError(
            f"members has shape {members.shape}, expected (N, *{reference.shape}) with "
            "the member axis leading"
        )
    n_members = members.shape[0]
    if n_members < 1:
        raise ValueError("crps needs at least one ensemble member, got an empty ensemble")

    # E|X - y|, estimated by the sample mean over members at every cell.
    skill = np.abs(members - reference[None]).mean(axis=0)

    if n_members == 1:
        # The pair term is empty, not zero-by-convention-with-a-divide: at one member the
        # score is |x - y| and the metric coincides with mean absolute error exactly.
        return float(skill.mean())

    # E|X - X'|, over ordered pairs excluding the diagonal. Sorting turns the O(N^2)
    # double sum into an O(N log N) weighted sum: for sorted members the total pairwise
    # absolute difference is sum_i (2i - N + 1) * x_(i), which matters because this runs
    # once per cell, per field, per severity level, per frame.
    ordered = np.sort(members, axis=0)
    weights = (2 * np.arange(n_members) - n_members + 1).astype(np.float64)
    weights = weights.reshape((n_members,) + (1,) * (members.ndim - 1))
    pair_sum = (weights * ordered).sum(axis=0)  # = 1/2 * sum_i sum_j |x_i - x_j|

    # Fair correction: divide the *ordered-pair* sum by N(N-1). pair_sum already halves
    # the double sum, so the factor here is 1/(N(N-1)) rather than 1/(2N(N-1)).
    spread = pair_sum / (n_members * (n_members - 1))
    return float((skill - spread).mean())
