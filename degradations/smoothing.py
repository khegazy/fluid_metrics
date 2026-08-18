"""Kernel smoothing.

Several kernels rather than one, because they differ in ways a metric can be blind to.
Gaussian is monotone in wavenumber; a box kernel has sinc sidelobes that *amplify* some
wavenumbers; a median filter is nonlinear and preserves the discontinuities a Gaussian
smears. A metric that responds identically to all of them at matched kernel width is only
seeing "amount of smoothing", while one that separates them is seeing structure -- which
is exactly the discrimination the panel is being selected for.

All kernels wrap at the boundary, matching the doubly periodic domain.

Widths are declared ``calibration="scale"``, so the config gives them as a fraction of the
field's characteristic scale and the ladder resolves them to cells per field. A fixed cell
count cannot serve both fields here: measured, density varies on ~136 cells against ~29 for
vorticity, so the previously configured sigmas reached a damage of 0.142 on vorticity and
0.012 on density -- an axis that carried no signal at all on the smoother field.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import convolve, gaussian_filter, median_filter, uniform_filter

from .registry import degradation


def _odd_width(severity: float) -> int:
    """Round a calibrated width to the nearest ODD number of cells, at least 1.

    A window of even width has no centre cell, so ``uniform_filter`` and ``median_filter``
    place it asymmetrically and the output is displaced by half a cell. For a project whose
    central concern is that metrics over-punish displacement, that shift dominates: measured on
    vorticity, calibrated widths that rounded to 2, 3, 6, 13 gave damage 0.0121, 0.0041,
    0.0338, 0.0880 -- non-monotone, because the even severity level carried a half-cell shift the odd one
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


@degradation(
    family="smoothing",
    severity_name="sigma",
    severity_units="cells",
    severity_direction="increasing",
    calibration="scale",
)
def gaussian_blur(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Isotropic Gaussian kernel smoothing.

    Monotone in wavenumber -- it attenuates every scale and amplifies none, which makes it
    the well-behaved reference against which the other kernels are read.
    """
    if severity <= 0:
        return x
    return gaussian_filter(x, sigma=severity, mode="wrap", axes=ctx.spatial_axes)


@degradation(
    family="smoothing",
    severity_name="width",
    severity_units="cells",
    severity_direction="increasing",
    calibration="scale",
)
def box_blur(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Square top-hat (moving average) smoothing.

    Its transfer function is a sinc, so it has sidelobes: some wavenumbers are amplified
    rather than attenuated, and the kernel is square rather than isotropic. Both are
    reasons a metric might distinguish it from a Gaussian of matched width.
    """
    width = _odd_width(severity)
    if width <= 1:
        return x
    size = [1] * x.ndim
    for axis in ctx.spatial_axes:
        size[axis] = width
    return uniform_filter(x, size=size, mode="wrap")


@degradation(
    family="smoothing",
    severity_name="width",
    severity_units="cells",
    severity_direction="increasing",
    calibration="scale",
)
def median_blur(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Median filter: nonlinear, and edge-preserving where a Gaussian smears.

    The interesting contrast for this project. A metric that scores median and Gaussian
    smoothing the same at matched width is not seeing the sharp structure that the
    shock-oriented metrics are supposed to target.
    """
    width = _odd_width(severity)
    if width <= 1:
        return x
    size = [1] * x.ndim
    for axis in ctx.spatial_axes:
        size[axis] = width
    return median_filter(x, size=size, mode="wrap")


@degradation(
    family="smoothing",
    severity_name="radius",
    severity_units="cells",
    severity_direction="increasing",
    calibration="scale",
)
def disk_blur(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Isotropic top-hat: a uniform disk, unlike box_blur's square."""
    if severity < 1:
        return x
    kernel = _radial_kernel(severity, ctx.grid.n_spatial, "disk")
    return _convolve_spatial(x, kernel)


@degradation(
    family="smoothing",
    severity_name="radius",
    severity_units="cells",
    severity_direction="increasing",
    calibration="scale",
)
def epanechnikov_blur(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Epanechnikov kernel, 3/4 (1 - u^2): the MSE-optimal smoothing kernel."""
    if severity < 1:
        return x
    kernel = _radial_kernel(severity, ctx.grid.n_spatial, "epanechnikov")
    return _convolve_spatial(x, kernel)


def _convolve_spatial(x: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Convolve each channel with a spatial kernel, wrapping at the boundary."""
    out = np.empty_like(x)
    for c in range(x.shape[0]):
        out[c] = convolve(x[c], kernel, mode="wrap")
    return out
