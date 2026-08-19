"""The `random_large_translation` degradation.

See ``card.md`` for what this stands in for, how its severity is scaled, and where it
is not a fair imitation of the failure it models.
"""

from __future__ import annotations

import numpy as np

from ..registry import degradation


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
