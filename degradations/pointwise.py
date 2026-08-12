"""Amplitude errors: correct position, wrong magnitude.

The complement of the translation family. Together they separate a metric's amplitude
sensitivity from its position sensitivity -- which is precisely the OT-1 pitfall the
tracker records, that a normalised Wasserstein distance accepts the wrong amplitude at the
right position. A metric that responds to `translate` but not to `gain` is measuring
position only, and needs an amplitude-sensitive partner in the panel.
"""

from __future__ import annotations

import numpy as np

from .registry import degradation


@degradation(
    family="pointwise",
    severity_name="gain error",
    severity_units="relative",
    severity_direction="increasing",
)
def gain(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Scale the fluctuation by ``1 + severity``, leaving the spatial mean intact.

    Pure amplitude error with zero position error: every feature stays exactly where it
    was and every gradient keeps its sign.
    """
    if severity == 0:
        return x
    spatial = tuple(range(1, x.ndim))
    mean = x.mean(axis=spatial, keepdims=True)
    return mean + (1.0 + severity) * (x - mean)


@degradation(
    family="pointwise",
    severity_name="offset",
    severity_units="fraction of fluctuation rms",
    severity_direction="increasing",
)
def bias(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Add a uniform offset scaled to the reference fluctuation RMS.

    Invisible to any metric built on fluctuations or gradients, which is the point: it
    separates metrics that track the absolute level from those that do not.
    """
    if severity == 0:
        return x
    return x + severity * ctx.fluctuation_rms


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
