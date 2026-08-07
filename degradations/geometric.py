"""Translations: the double-penalty probe.

This is the project's central pathology made into a controlled experiment. A pure
translation leaves shape and amplitude exactly correct and moves only position, so a
metric's response to it separates "position error" from every other kind.

Measured on the real 256^2 vorticity field, normalised MSE (1.0 = the value two unrelated
fields get) against displacement:

======  =====  =====  =====  =====  =====  =====  =====  =====
cells   0.125  0.25   0.5    1      2      4      16     64
MSE     0.001  0.003  0.012  0.045  0.147  0.311  0.601  0.973
======  =====  =====  =====  =====  =====  =====  =====  =====

So L2 is already a third of the way to "completely unrelated" for a 4-cell displacement of
a field whose structures are far larger than 4 cells -- the double penalty, quantified. It
saturates over tens of cells rather than immediately, because this weakly compressible
field has a long correlation length; a shocked field would saturate far faster.

Sub-cell resolution matters because that is where a displacement-aware metric should still
report near-zero while L2 is already climbing. Integer rolls cannot sample it, so
`shift_response` would be a handful of points rather than a curve. The sub-pixel operator
reproduces the integer one exactly at integer distances (verified above: 0.045 at 1 cell,
0.147 at 2, 0.311 at 4, matching `translate` to three decimals), so the two are one curve.

Rotation is deliberately absent. It requires rotating the velocity *components*, not just
resampling the grid, and forgetting that produces a plausible-looking field that is
physically wrong. See issues/015-rotation-degradation.md.
"""

from __future__ import annotations

import numpy as np

from .registry import degradation


def _axes_for(direction: str, ctx) -> tuple[int, ...]:
    """Resolve a direction name to negative array axes via the grid's dims.

    Never hardcode -1 or -2: which axis is "x" depends on how many spatial dimensions
    there are.
    """
    if direction == "diag":
        return ctx.spatial_axes
    return (ctx.axis(direction),)


@degradation(
    family="geometric",
    severity_name="distance",
    severity_units="cells",
    severity_direction="increasing",
    defaults={"axis": "x"},
)
def translate(x: np.ndarray, severity: float, *, ctx, axis: str = "x") -> np.ndarray:
    """Whole-cell periodic translation.

    Exact and cheap, but quantised: on a periodic grid ``translate(x, N) == x``, and the
    smallest nonzero displacement is one cell.
    """
    shift = int(round(severity))
    if shift == 0:
        return x
    axes = _axes_for(axis, ctx)
    return np.roll(x, shift=(shift,) * len(axes), axis=axes)


@degradation(
    family="geometric",
    severity_name="distance",
    severity_units="cells",
    severity_direction="increasing",
    defaults={"axis": "x"},
)
def translate_subpixel(
    x: np.ndarray, severity: float, *, ctx, axis: str = "x"
) -> np.ndarray:
    """Fractional translation by a Fourier phase shift -- exact on a periodic grid.

    Resolves the sub-cell region where the double-penalty curve actually distinguishes
    metrics. At integer distances it reproduces ``np.roll`` to floating-point tolerance,
    which the contract test pins.
    """
    if severity == 0:
        return x
    axes = _axes_for(axis, ctx)
    spatial = tuple(range(1, x.ndim))
    spectrum = np.fft.fftn(x, axes=spatial)

    for ax in axes:
        n = x.shape[ax]
        freq = np.fft.fftfreq(n)
        # Broadcast the phase ramp along this axis only.
        shape = [1] * x.ndim
        shape[ax] = n
        phase = np.exp(-2j * np.pi * freq.reshape(shape) * severity)
        spectrum = spectrum * phase

    return np.real(np.fft.ifftn(spectrum, axes=spatial))
