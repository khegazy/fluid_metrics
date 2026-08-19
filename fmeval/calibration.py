"""Per-field spectral properties, so severities mean the same thing on every field.

Severities written in absolute units -- a wavenumber, a number of cells -- land in wildly
different places depending on where a field keeps its energy. Measured on the production
trajectory, 99% of the density fluctuation energy sits below wavenumber 6 while vorticity
needs wavenumber 63, and the energy-weighted characteristic scale differs by a factor of
about five (~136 cells against ~29). One fixed list therefore cannot serve both: the
configured high-pass cutoffs saturated by the second severity level on density, making two of four
severity levels the same experiment, while the configured blur reached only 1.2% of the
unrelated-field level there, making that axis carry no signal at all.

The fix is to express those severities relative to a property of the field and resolve them
against a measurement. This module is that measurement. An operator declares which property
it scales with (see ``DegradationSpec.calibration``) and the ladder resolves its nominal
severities per field.

**Calibration is measured once per (field, analysis grid) and then held fixed** for the whole
run. Re-measuring per frame would make the ladder itself drift as the flow evolves, so two
frames would no longer be running the same experiment and the per-frame rank correlation --
which is the primary acceptance statistic -- would be comparing different ladders.

The spread across the sampled frames is recorded, because it is the diagnostic for whether
holding the calibration fixed is defensible on a given trajectory. A field whose spectrum
moves substantially over the frames being evaluated cannot be calibrated once, and the run
should say so rather than quietly average over it.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field as dc_field

import numpy as np

from .data.base import GridSpec
from .wavenumbers import wavenumber_magnitude

log = logging.getLogger(__name__)

#: Fractional spread across sampled frames above which a single calibration is doubtful.
DRIFT_WARN = 0.25


@dataclass(frozen=True)
class FieldCalibration:
    """Spectral properties of one field on one analysis grid.

    Attributes:
        field: Canonical field name.
        n_frames: How many frames the measurement averaged over.
        wavenumbers: The distinct wavevector magnitudes present on the grid, ascending. Not
            integers: the diagonal modes sit between the shells, and a filter cutoff is compared
            against these exact values.
        cumulative_energy: Cumulative fraction of fluctuation energy at or below the matching
            entry of ``wavenumbers``. Averaged over the sampled frames.
        mean_wavenumber: Energy-weighted mean wavenumber.
        characteristic_scale: ``N / mean_wavenumber`` in cells -- the scale the field varies
            on, and the natural unit for a smoothing width.
        scale_spread: Relative spread of ``characteristic_scale`` across the sampled frames.
            Above :data:`DRIFT_WARN` a single calibration is not trustworthy.
    """

    field: str
    n_frames: int
    wavenumbers: np.ndarray
    cumulative_energy: np.ndarray
    mean_wavenumber: float
    characteristic_scale: float
    scale_spread: float

    def wavenumber_for_energy_fraction(self, fraction: float) -> float:
        """Wavenumber below which ``fraction`` of the fluctuation energy lies.

        Interpolated between shells, so the result is fractional. A smooth filter can use it
        directly; a sharp one rounds, which is where the quantisation of
        :meth:`quantised_cutoff` comes from.

        Args:
            fraction: In [0, 1]. Clamped to the usable range [1, k_max] at the ends rather
                than returning a degenerate cutoff of 0 or beyond Nyquist.
        """
        if not 0.0 <= fraction <= 1.0:
            raise ValueError(f"energy fraction must be in [0, 1], got {fraction}")
        k = float(np.interp(fraction, self.cumulative_energy, self.wavenumbers))
        return float(np.clip(k, 1.0, float(self.wavenumbers[-1])))

    def cutoff_removing_energy(self, fraction: float, side: str) -> float:
        """Cutoff wavenumber at which a filter removes ``fraction`` of the energy.

        This is the inversion the ladder actually needs, and getting the side wrong silently
        inverts the axis: a low-pass removes what lies ABOVE its cutoff, so a severity of
        "remove 5%" is the wavenumber holding 95% of the energy, not the one holding 5%.

        Args:
            fraction: Fraction of fluctuation energy the operator should destroy.
            side: ``"above"`` for a low-pass (it removes the small scales) or ``"below"`` for
                a high-pass (it removes the large ones).
        """
        if side == "above":
            return self.wavenumber_for_energy_fraction(1.0 - fraction)
        if side == "below":
            return self.wavenumber_for_energy_fraction(fraction)
        raise ValueError(f"side must be 'above' or 'below', got {side!r}")

    def energy_removed(self, cutoff: float, side: str) -> float:
        """Fraction of energy a sharp filter at ``cutoff`` removes.

        Exact for an ideal filter, because the curve is tabulated at the same magnitudes the
        filter compares against. Predicted rather than measured -- the run also records what each
        severity level measurably removed, in the ``energy_removed`` result column.
        """
        index = int(np.searchsorted(self.wavenumbers, cutoff, side="right")) - 1
        if index < 0:
            below = 0.0
        else:
            below = float(self.cumulative_energy[min(index, len(self.cumulative_energy) - 1)])
        return below if side == "below" else 1.0 - below

    def quantised_cutoff(self, cutoff: float) -> float:
        """The largest available magnitude at or below ``cutoff``.

        Two cutoffs that quantise alike select exactly the same modes and are therefore the same
        experiment, whatever their nominal severities were.
        """
        index = int(np.searchsorted(self.wavenumbers, cutoff, side="right")) - 1
        if index < 0:
            return 0.0
        return float(self.wavenumbers[index])

    def length_for_scale_fraction(self, fraction: float) -> float:
        """A length in cells, as a fraction of the characteristic scale."""
        return float(fraction) * self.characteristic_scale

    def summary(self) -> dict[str, float | int | str]:
        """Flat record for provenance and for the report."""
        return {
            "field": self.field,
            "n_frames": self.n_frames,
            "mean_wavenumber": self.mean_wavenumber,
            "characteristic_scale": self.characteristic_scale,
            "scale_spread": self.scale_spread,
            "k_energy_50": self.wavenumber_for_energy_fraction(0.5),
            "k_energy_90": self.wavenumber_for_energy_fraction(0.9),
            "k_energy_99": self.wavenumber_for_energy_fraction(0.99),
        }


def _binned_energy(field: np.ndarray, inverse: np.ndarray, n_bins: int) -> np.ndarray:
    """Energy of the *fluctuation*, grouped by exact wavevector magnitude.

    The spatial mean is removed first. Leaving it in would put an overwhelming spike at k=0 for a
    field like density, which is 1.0 with fluctuations of order 1e-4, and every energy fraction
    would then resolve to the same wavenumber.

    Args:
        field: ``(C, *spatial)``.
        inverse: For each mode, the index of its magnitude in the sorted distinct magnitudes.
        n_bins: How many distinct magnitudes there are.
    """
    spatial = tuple(range(1, field.ndim))
    fluct = field - field.mean(axis=spatial, keepdims=True)
    power = sum(
        np.abs(np.fft.fftn(channel, axes=tuple(range(channel.ndim)))) ** 2
        for channel in fluct
    )
    return np.bincount(inverse.ravel(), power.ravel(), minlength=n_bins)


def _magnitude_bins(grid: GridSpec) -> tuple[np.ndarray, np.ndarray]:
    """The distinct wavevector magnitudes on the grid, and each mode's index into them.

    Grouping by exact magnitude rather than by rounded shell is what keeps the calibration and
    the filters talking about the same thing; see :mod:`fmeval.wavenumbers`.
    """
    magnitude = wavenumber_magnitude(tuple(grid.shape))
    values, inverse = np.unique(np.round(magnitude, 9), return_inverse=True)
    return values, inverse.reshape(magnitude.shape)


def calibrate_field(frames: Sequence[np.ndarray], grid: GridSpec,
                    field: str) -> FieldCalibration:
    """Measure the spectral properties of one field from a sample of frames.

    Args:
        frames: Arrays of shape ``(C, *spatial)`` on ``grid``, from different times.
        grid: The analysis grid the severities will be expressed on.
        field: Canonical field name, for reporting.

    Raises:
        ValueError: If no frames are given, or the field is spatially uniform in all of them
            and therefore has no spectrum to calibrate against.
    """
    if not frames:
        raise ValueError(f"cannot calibrate {field!r} without any frames")

    shells, inverse = _magnitude_bins(grid)
    n_bins = len(shells)

    energies, scales = [], []
    for frame in frames:
        energy = _binned_energy(frame, inverse, n_bins)
        total = energy.sum()
        if total <= 0:
            continue
        energies.append(energy / total)
        mean_k = float((shells * energy).sum() / total)
        if mean_k > 0:
            scales.append(grid.shape[0] / mean_k)

    if not energies or not scales:
        raise ValueError(
            f"{field!r} has no fluctuation energy in the sampled frames, so there is "
            "nothing to calibrate severities against. Exclude it, or use absolute "
            "severities for the axes that would scale with it."
        )

    mean_energy = np.mean(energies, axis=0)
    cumulative = np.cumsum(mean_energy)
    cumulative /= cumulative[-1]
    scale = float(np.mean(scales))
    spread = float(np.std(scales) / scale) if scale > 0 else 0.0

    if spread > DRIFT_WARN:
        log.warning(
            "%s: characteristic scale varies by %.0f%% across the %d calibration frames "
            "(%.1f cells mean). A single calibration is questionable for this field; the "
            "spread is recorded as calibration.scale_spread.",
            field, 100 * spread, len(scales), scale,
        )

    mean_k = grid.shape[0] / scale
    return FieldCalibration(
        field=field,
        n_frames=len(energies),
        wavenumbers=shells,
        cumulative_energy=cumulative,
        mean_wavenumber=mean_k,
        characteristic_scale=scale,
        scale_spread=spread,
    )


@dataclass
class Calibration:
    """Calibrations for every field in a run, keyed by canonical name."""

    fields: dict[str, FieldCalibration] = dc_field(default_factory=dict)

    def __getitem__(self, field: str) -> FieldCalibration:
        if field not in self.fields:
            raise KeyError(
                f"no calibration for {field!r}; it was not measured. Fields calibrated: "
                f"{sorted(self.fields)}"
            )
        return self.fields[field]

    def __contains__(self, field: str) -> bool:
        return field in self.fields

    def summary(self) -> list[dict[str, float | int | str]]:
        return [c.summary() for c in self.fields.values()]

    def spectrum_frame(self) -> list[dict[str, float | int | str]]:
        """The cumulative energy curve as flat rows, one per (field, wavenumber).

        Written out so a reader can see *why* a cutoff ladder has the resolution it has. On this
        data the curve is what makes the density case obvious at a glance: its fluctuation energy
        is 69% in the four diagonal modes at |k| = sqrt(2) and only 3e-5 in the axis modes just
        below them, so consecutive available cutoffs there differ by most of the field.
        """
        rows = []
        for cal in self.fields.values():
            for k, fraction in zip(cal.wavenumbers, cal.cumulative_energy):
                rows.append({
                    "field": cal.field,
                    "wavenumber": float(k),
                    "cumulative_energy_below": float(fraction),
                })
        return rows


def calibrate(frames_by_field: dict[str, list[np.ndarray]], grid: GridSpec,
              fields: Sequence[str]) -> Calibration:
    """Calibrate each requested field, skipping any that has no usable spectrum."""
    out = Calibration()
    for field in fields:
        frames = frames_by_field.get(field, [])
        try:
            out.fields[field] = calibrate_field(frames, grid, field)
        except ValueError as exc:
            log.warning("skipping calibration for %s: %s", field, exc)
    return out
