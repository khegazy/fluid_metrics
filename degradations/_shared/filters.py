"""Spectral filtering, shared by the low-pass, high-pass and band operators.

One definition of the wavenumber magnitude, re-exported from :mod:`fmeval.wavenumbers`,
because the filters and the severity calibration once used two and disagreed about which
side of a cutoff the diagonal modes fell on.
"""

from __future__ import annotations

import numpy as np

from fmeval.wavenumbers import wavenumber_magnitude

_wavenumber_magnitude = wavenumber_magnitude


def _apply_filter(x: np.ndarray, transfer: np.ndarray,
                  *, keep_mean: bool = False) -> np.ndarray:
    """Multiply each channel's spectrum by a real transfer function.

    Args:
        x: Field, ``(C, *spatial)``.
        transfer: Real transfer function on the spatial wavenumber grid.
        keep_mean: Force the k=0 mode through unchanged, preserving the spatial mean.
            Required for the high-pass family; see the note there.
    """
    spatial = tuple(range(1, x.ndim))
    if keep_mean:
        transfer = transfer.copy()
        transfer[(0,) * transfer.ndim] = 1.0
    spectrum = np.fft.fftn(x, axes=spatial)
    return np.real(np.fft.ifftn(spectrum * transfer, axes=spatial))
