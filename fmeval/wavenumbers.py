"""The one definition of wavenumber magnitude, shared by the filters and the calibration.

There were two, and they disagreed. The spectral operators compared a *continuous* ``|k|``
against their cutoff while the calibration binned energy into shells of ``rint(|k|)``, so the
diagonal modes fell on opposite sides of the same number: on a 256 grid the mode ``(1, 1)`` has
``|k| = 1.414`` and belongs to shell 1, and a cutoff of 1.06 therefore kept the whole shell
according to the calibration and dropped most of it in fact.

That is not a rounding nuisance. Measured on density, whose fluctuation energy is concentrated in
the lowest shells, a low-pass asked to remove 30% removed 99.997% -- the two mildest requests came
out as near-total destruction, and every number in between looked plausible. Both sides now use
this module, so the energy a cutoff removes according to the calibration is the energy it actually
removes.
"""

from __future__ import annotations

import numpy as np


def wavenumber_magnitude(shape: tuple[int, ...]) -> np.ndarray:
    """Grid of ``|k|`` in integer wavenumber units -- cycles across the domain.

    Args:
        shape: Spatial shape, in the canonical trailing-axes order.

    Returns:
        Array of ``shape`` holding the Euclidean magnitude of each mode's wavevector. Not
        rounded: the magnitudes a filter cutoff is actually compared against.
    """
    axes = np.meshgrid(*[np.fft.fftfreq(n) * n for n in shape], indexing="ij")
    return np.sqrt(sum(a**2 for a in axes))
