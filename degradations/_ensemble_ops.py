"""Shared implementation of the dispersion-scaling operators.

Leading underscore so :func:`degradations.registry.discover` skips it: this is a helper
shared by the ``spread_inflate`` and ``spread_deflate`` bundles, not a bundle of its own.
"""

from __future__ import annotations

import numpy as np


def scale_spread(members: np.ndarray, factor: float) -> np.ndarray:
    """Scale an ensemble's dispersion about its own mean, leaving that mean fixed.

    .. math::

        m_i' = \\bar{m} + \\alpha\\,(m_i - \\bar{m})

    The ensemble mean is preserved exactly (to round-off), which is what makes this a
    pure calibration axis: nothing about the ensemble's central prediction changes, so a
    metric that responds is responding to dispersion alone. At ``factor=0`` the ensemble
    collapses onto its mean -- a forecast claiming perfect certainty.

    Args:
        members: Ensemble members, ``(N, C, *spatial)`` with the member axis leading.
        factor: Multiplier on the deviations. One is a no-op.

    Returns:
        The rescaled ensemble, same shape.
    """
    mean = members.mean(axis=0, keepdims=True)
    return mean + factor * (members - mean)
