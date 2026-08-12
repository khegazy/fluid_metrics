"""Random perturbations, and the IN-4 canary.

Noise severities are relative to the **fluctuation** RMS, never the raw RMS. Density on
this data is 1.0 +/- 1.8e-4, so ``0.001 * RMS(raw)`` would be five times the entire signal
and the mildest rung would already be total destruction -- the ladder would be flat-topped
and non-monotone for every metric. That single choice decides whether the noise axis
produces usable data at all.
"""

from __future__ import annotations

import numpy as np

from .registry import degradation


@degradation(
    family="stochastic",
    severity_name="amplitude",
    severity_units="fraction of fluctuation rms",
    severity_direction="increasing",
    stochastic=True,
)
def additive_noise(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Gaussian noise scaled to a fraction of the reference fluctuation RMS."""
    if severity <= 0:
        return x
    return x + severity * ctx.fluctuation_rms * ctx.rng.standard_normal(x.shape)


@degradation(
    family="stochastic",
    severity_name="amplitude",
    severity_units="relative",
    severity_direction="increasing",
    stochastic=True,
)
def multiplicative_noise(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Multiply by ``1 + severity * N(0, 1)``: error proportional to the local value."""
    if severity <= 0:
        return x
    return x * (1.0 + severity * ctx.rng.standard_normal(x.shape))


@degradation(
    name="gaussian_impostor",
    family="stochastic",
    severity_name="n/a",
    severity_units="",
    severity_direction="increasing",
    ordinal=False,  # a pass/fail canary, NOT a rung on any monotone axis
    stochastic=True,
    defaults={"match_moments": True},
)
def gaussian_impostor(
    x: np.ndarray, severity: float, *, ctx, match_moments: bool = True
) -> np.ndarray:
    """IN-4: a spectrum-matched Gaussian random field.

    Keeps ``|X_k|`` exactly -- hence the energy spectrum, the two-point correlation, and
    every isotropic spectral diagnostic -- and replaces the phases with those of a white
    Gaussian field. The result has the right spectrum and no phase coupling: on this data
    its flatness is 3.01 against the reference's 17.06. It is not turbulence, and any
    metric that scores it near the reference is phase-blind and must not be used alone.

    **The gotcha this implementation exists to avoid:** take the phases from ``rfftn`` of a
    *real* Gaussian field rather than drawing ``exp(i U(0, 2pi))`` directly. Hand-drawn
    phases violate Hermitian symmetry at the self-conjugate modes (k=0, the Nyquist
    row/column, and the Nyquist corners), so ``irfftn`` silently discards imaginary parts
    and corrupts the very amplitude spectrum you were preserving. A first attempt that way
    produced flatness 47.9 instead of 3. Deriving the phase from a real field gets all the
    symmetry constraints right for free.

    ``ordinal=False``: this is excluded from every Spearman computation. Folding it into a
    family as "level 6" would silently corrupt every rank correlation it touched.

    **Which metrics this actually catches.** Not L2. Measured on the real vorticity field,
    MSE scores the impostor at 0.976 of chance -- it rejects it firmly, because a
    phase-randomised field is pointwise uncorrelated with the original. The canary is aimed
    at metrics that see only second-order statistics: an energy spectrum (BD-1) or a
    two-point correlation (BD-2) scores the impostor *perfectly*, since those are exactly
    what it preserves. Read the canary column alongside the displacement column: L2 passes
    the canary and fails on displacement, and a spectral metric does the reverse.
    """
    spatial = tuple(range(1, x.ndim))
    shape = x.shape[1:]
    out = np.empty_like(x)
    for c in range(x.shape[0]):
        amplitude = np.abs(np.fft.rfftn(x[c], axes=tuple(range(len(shape)))))
        noise = ctx.rng.standard_normal(shape)
        noise_spectrum = np.fft.rfftn(noise, axes=tuple(range(len(shape))))
        phase = noise_spectrum / (np.abs(noise_spectrum) + 1e-300)
        y = np.fft.irfftn(amplitude * phase, s=shape, axes=tuple(range(len(shape))))
        if match_moments:
            # Restore mean and fluctuation variance exactly; irfftn is real by
            # construction here, so this only corrects round-off.
            y = y - y.mean()
            scale = y.std()
            if scale > 0:
                y = y * (x[c].std() / scale)
            y = y + x[c].mean()
        out[c] = y
    return out
