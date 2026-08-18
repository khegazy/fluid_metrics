"""Baseline pointwise error metrics.

These are the L^p family that the rest of the tracker exists to beat. They doubly penalise
a shock or eddy that is correct in shape and amplitude but slightly displaced -- the
"double penalty" of weather verification, the "cycle skipping" of seismic inversion (see
CLAUDE.md, "Core problem framing"). They are in the panel as the *control*, not as
candidates: a suite in which L2 looks good everywhere is a broken suite.

All four are pointwise-decomposable, so each ships a per-cell density map. For a displaced
sharp feature the MSE map shows two lobes -- one where the feature should be and is not,
one where it is and should not be -- which is the double penalty as a picture.

These four are *controls* rather than candidates: they are the pointwise baseline that
candidate metrics are read against, not metrics competing for a panel slot of their own.
Their cards carry ``status: control``; see issues/021-tracker-ids-for-baselines.md.
"""

from __future__ import annotations

import numpy as np

from .registry import metric, pointwise_map


@metric(
    name="mae",
    arity="pairwise",
    fields=("*",),
    returns="scalar",
    differentiable=True,
    cost="cheap",
    higher_is_better=False,
    symmetric=True,
    units="field",
    reduction="mean",
)
def mae(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Mean absolute error over all channels and cells (L1 / N)."""
    return float(np.abs(reference - candidate).mean())


@pointwise_map(of="mae")
def mae_map(reference: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    """Per-cell absolute error, summed over channels. Reduces to `mae` by mean/C."""
    return np.abs(reference - candidate).sum(axis=0)


@metric(
    name="mse",
    arity="pairwise",
    fields=("*",),
    returns="scalar",
    differentiable=True,
    cost="cheap",
    higher_is_better=False,
    symmetric=True,
    units="field^2",
    reduction="mean",
)
def mse(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Mean squared error over all channels and cells ((L2)^2 / N)."""
    d = reference - candidate
    return float(np.mean(d * d))


@pointwise_map(of="mse")
def mse_map(reference: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    """Per-cell squared error, summed over channels. Reduces to `mse` by mean/C."""
    return ((reference - candidate) ** 2).sum(axis=0)


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
    """Root mean squared error; same units as the field."""
    return float(np.sqrt(mse(reference, candidate)))


@pointwise_map(of="rmse")
def rmse_map(reference: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    """Per-cell *squared* error, summed over channels.

    Note the reduction is `sqrt_mean`, not `mean`: this map does NOT average to the metric
    value. That mismatch is exactly why the reduction is declared rather than assumed.
    """
    return ((reference - candidate) ** 2).sum(axis=0)


@metric(
    name="nrmse",
    arity="pairwise",
    fields=("*",),
    returns="scalar",
    differentiable=True,
    cost="cheap",
    higher_is_better=False,
    symmetric=False,
    units="dimensionless",
)
def nrmse(reference: np.ndarray, candidate: np.ndarray) -> float:
    """RMSE normalised by the RMS of the reference *fluctuation*.

    The spatial mean is removed before normalising because the kinet weakly compressible
    data has density = 1.0 +/- 1.8e-4: normalising by the raw RMS (~1.0) would hide four
    orders of magnitude of relative error and make density and velocity results
    incomparable on the same axis. Not symmetric -- the reference sets the scale.

    Returns NaN for a spatially uniform reference, where no fluctuation scale exists.
    """
    spatial = tuple(range(1, reference.ndim))
    fluct = reference - reference.mean(axis=spatial, keepdims=True)
    denom = float(np.sqrt((fluct**2).mean()))
    if denom == 0.0:
        return float("nan")
    return rmse(reference, candidate) / denom
