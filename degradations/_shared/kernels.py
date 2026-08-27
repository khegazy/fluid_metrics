"""Kernel construction and convolution, shared by the smoothing operators.

Every kernel here wraps at the boundary, matching the doubly periodic domain.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import convolve


def _odd_width(severity: float) -> int:
    """Round a calibrated width to the nearest ODD number of cells, at least 1.

    A window of even width has no centre cell, so ``uniform_filter`` and ``median_filter``
    place it asymmetrically and the output is displaced by half a cell. For a project whose
    central concern is that metrics over-punish displacement, that shift dominates: measured on
    vorticity, calibrated widths that rounded to 2, 3, 6, 13 gave damage 0.0121, 0.0041,
    0.0338, 0.0880 -- non-monotone, because the even severity level carried a half-cell
    shift the odd one
    did not. Rounding to odd removes the artefact and the axis becomes monotone.
    """
    width = int(round(severity))
    if width <= 1:
        return 1
    return width if width % 2 == 1 else width + 1


def _radial_kernel(radius: float, n_spatial: int, profile: str) -> np.ndarray:
    """Build a normalised isotropic kernel of the given profile."""
    r = int(np.ceil(radius))
    axes = np.meshgrid(*[np.arange(-r, r + 1)] * n_spatial, indexing="ij")
    dist = np.sqrt(sum(a.astype(float) ** 2 for a in axes))
    u = dist / radius
    if profile == "disk":
        k = (u <= 1.0).astype(float)
    elif profile == "epanechnikov":
        # Epanechnikov: 3/4 (1 - u^2) on |u| <= 1; the MSE-optimal smoothing kernel.
        k = np.where(u <= 1.0, 0.75 * (1.0 - u**2), 0.0)
    else:  # pragma: no cover - guarded by the caller
        raise ValueError(f"unknown kernel profile {profile!r}")
    total = k.sum()
    if total == 0:
        raise ValueError(f"kernel with radius {radius} is empty")
    return k / total


def _convolve_spatial(x: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Convolve each channel with a spatial kernel, wrapping at the boundary."""
    out = np.empty_like(x)
    for c in range(x.shape[0]):
        out[c] = convolve(x[c], kernel, mode="wrap")
    return out
