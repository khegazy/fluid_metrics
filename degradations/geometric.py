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


@degradation(
    name="random_large_translation",
    family="geometric",
    severity_name="draw",
    severity_units="",
    severity_direction="increasing",
    ordinal=False,   # a reference measurement, not a severity level on a monotone axis
    stochastic=True,
)
def random_large_translation(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Translate by a large random offset on every axis: the statistically identical,
    positionally unrelated field.

    Used to *measure* the value a metric gives two fields that share all statistics but no
    alignment, which is the anchor the dimensionless damage score is defined against. On a
    periodic domain a translation preserves every single- and multi-point statistic
    exactly, so this is a perfect statistical match by construction -- verified on the real
    data as variance ratio 1.000000 and flatness matching the reference to three decimals.

    A distant frame of the same trajectory would be the obvious alternative and is wrong:
    the flow decays, so from t=5000 to t=9000 the vorticity variance falls to 0.70 of its
    value and the flatness rises from 17.1 to 27.3. That field is a different physical
    state, not a twin, and it scores *closer* to the reference than a true twin does
    purely because it has weakened.

    Offsets are drawn from the middle half of each axis, and ``severity`` is just the draw
    index so that several independent draws can be averaged -- which is how the anchor is
    actually estimated. Six draws on the real vorticity field agree to within 0.96-1.03,
    so the estimate is well determined there.

    **Caveat: this decorrelates only a broadband field.** For a field dominated by a single
    large-scale mode the residual correlation after translation is ``cos(2*pi*d/L)``, which
    no choice of offset makes reliably small, so the anchor would be biased and would swing
    between draws. Real turbulence is broadband and this is not a concern for the datasets
    here, but a strongly single-mode field would need a different construction -- an
    independent realisation of the same physics, which the data does not currently provide
    (see issues/004-independent-realizations.md). The spread across draws is the diagnostic:
    if it is wide, the anchor is not trustworthy for that field.
    """
    offsets = [
        int(ctx.rng.integers(n // 4, 3 * n // 4 + 1)) for n in x.shape[1:]
    ]
    return np.roll(x, shift=tuple(offsets), axis=ctx.spatial_axes)
