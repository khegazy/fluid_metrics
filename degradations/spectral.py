"""Spectral band manipulation: low-pass, high-pass, and band attenuation.

Low-pass is the realistic over-smoothing failure of an ML surrogate. High-pass removes the
energy-containing large scales, which is *not* a realistic surrogate failure but is a
direct probe of whether a metric sees large-scale structure at all.

Both an ideal (sharp cutoff) and a Butterworth (smooth rolloff) variant ship, because the
ideal filters ring -- Gibbs oscillations near sharp features -- and the Butterworth pair is
the ringing-free control. The contrast is itself informative for a project whose central
object is a sharp feature.

**Severities are the fraction of fluctuation energy removed, not a wavenumber.** Both
directions therefore mean the same thing and rise with damage, and the same config number
lands in the same relative place on every field. A wavenumber cannot: measured, 99% of the
density fluctuation energy sits below k = 6 against k = 63 for vorticity, so the previously
configured cutoffs [2, 4, 8, 16] removed 0.278/0.475/0.684/0.811 of vorticity energy -- a good
spread -- but 0.697/0.947/0.997/1.000 of density energy, saturating at the second severity level so two
of the four were the same experiment run twice. The ladder resolves the fraction to a cutoff
per field against the measured spectrum; the resolved wavenumber is recorded on every row.

Note these operators applied per channel to a velocity field break the divergence
constraint. At Ma = 0.1 that is acceptable and arguably makes the probe harder; isolating
the effect needs a Leray projection, which kinet does not provide and which is therefore
left to issues/024-leray-projection.md rather than shipped untested.
"""

from __future__ import annotations

import numpy as np

from fmeval.wavenumbers import wavenumber_magnitude

from .registry import degradation


#: Re-exported under its old private name so the filters below read unchanged. The definition
#: lives in fmeval so the severity calibration compares against exactly the same magnitudes; two
#: definitions of |k| silently disagreed about the diagonal modes. See fmeval/wavenumbers.py.
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


@degradation(
    family="spectral",
    severity_name="energy removed",
    severity_units="fraction",
    severity_direction="increasing",
    calibration="energy_above",
)
def lowpass_ideal(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Sharp low-pass: zero every mode above the cutoff, removing the small scales.

    Rings near sharp features (Gibbs). Compare against `lowpass_butterworth` to separate
    "lost small scales" from "gained ringing".

    ``severity`` reaches this function already resolved to a cutoff wavenumber by the ladder,
    from the requested fraction of energy to remove.
    """
    k = _wavenumber_magnitude(ctx.grid.shape)
    return _apply_filter(x, (k <= severity).astype(float))


@degradation(
    family="spectral",
    severity_name="energy removed",
    severity_units="fraction",
    severity_direction="increasing",
    calibration="energy_above",
    defaults={"order": 4},
)
def lowpass_butterworth(x: np.ndarray, severity: float, *, ctx, order: int = 4) -> np.ndarray:
    """Smooth low-pass, ``1 / (1 + (k/k_c)^(2n))``. No ringing: the ideal filter's control."""
    k = _wavenumber_magnitude(ctx.grid.shape)
    with np.errstate(divide="ignore", over="ignore"):
        transfer = 1.0 / (1.0 + (k / max(severity, 1e-12)) ** (2 * order))
    return _apply_filter(x, transfer)


@degradation(
    family="spectral",
    severity_name="energy removed",
    severity_units="fraction",
    severity_direction="increasing",
    calibration="energy_below",
)
def highpass_ideal(x: np.ndarray, severity: float, *, ctx) -> np.ndarray:
    """Sharp high-pass: zero every mode with |k| < cutoff, keeping the spatial mean.

    Removes the energy-containing large scales. Not a realistic surrogate failure, but a
    direct test of whether a metric registers large-scale structure at all.

    **The k=0 mode is preserved deliberately.** Deleting it removes the spatial mean, which
    for a field like density (1.0 with fluctuations of 2e-4) is a change four orders of
    magnitude larger than anything the cutoff controls. Measured before this was fixed:
    every severity level gave an identical damage of 2.7e7 relative to the unrelated-field level, so
    the axis carried no ordering at all and its rank correlation collapsed to 0.10. Keeping
    the mean makes the operator measure what it is named for -- removal of large-scale
    structure -- and restores a monotone ladder on every field.
    """
    k = _wavenumber_magnitude(ctx.grid.shape)
    return _apply_filter(x, (k >= severity).astype(float), keep_mean=True)


@degradation(
    family="spectral",
    severity_name="energy removed",
    severity_units="fraction",
    severity_direction="increasing",
    calibration="energy_below",
    defaults={"order": 4},
)
def highpass_butterworth(
    x: np.ndarray, severity: float, *, ctx, order: int = 4
) -> np.ndarray:
    """Smooth high-pass, ``1 - 1/(1 + (k/k_c)^(2n))``, keeping the spatial mean.

    The k=0 mode is preserved for the same reason as in :func:`highpass_ideal`.
    """
    k = _wavenumber_magnitude(ctx.grid.shape)
    with np.errstate(divide="ignore", over="ignore"):
        transfer = 1.0 - 1.0 / (1.0 + (k / max(severity, 1e-12)) ** (2 * order))
    return _apply_filter(x, transfer, keep_mean=True)


@degradation(
    family="spectral",
    severity_name="retained fraction",
    severity_units="",
    severity_direction="decreasing",  # retaining LESS is worse
    defaults={"k_lo": 16.0, "k_hi": 64.0},
)
def band_attenuate(
    x: np.ndarray, severity: float, *, ctx, k_lo: float = 16.0, k_hi: float = 64.0
) -> np.ndarray:
    """Scale the amplitude of one wavenumber band by ``severity``, leaving the rest alone.

    The direct experimental test of the NM-3 / BD-3 organising principle: damage a single
    scale band and a genuinely scale-selective metric should respond only when the band it
    targets is the one damaged. A metric whose response is the same wherever the damage
    sits is measuring "badness in general".
    """
    k = _wavenumber_magnitude(ctx.grid.shape)
    transfer = np.ones_like(k)
    transfer[(k >= k_lo) & (k <= k_hi)] = severity
    return _apply_filter(x, transfer)
