"""Panel rows for an exemplar figure, one function per diagnostic.

An exemplar panel shows what a degradation does to a field: columns are the original and
three severities, rows are the field itself followed by whichever diagnostics expose the
mechanism. A blur is legible in a radial spectrum; a translation is not, because it moves
spectral phase rather than amplitude, and its spectrum row would be four identical curves.
Choosing the wrong row makes a figure that says nothing, so the choice is declared per
degradation in ``card.yaml`` and rendered here.

Adding a diagnostic is one decorated function in this module and one entry in the card
schema's vocabulary. The registry pattern is the same one the metric, degradation and
report-renderer registries use, so there is no import list to update.

Every diagnostic returns the numbers behind what it drew. Figures are for people; the
numbers are for agents, which cannot open a PNG, and both come from the same call so they
cannot disagree.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any

import numpy as np

from fmeval.report import style
from fmeval.wavenumbers import wavenumber_magnitude

DIAGNOSTICS: dict[str, DiagnosticSpec] = {}
"""Every registered diagnostic, by the name a card uses."""


@dataclass(frozen=True)
class DiagnosticSpec:
    """One panel row: how to draw it, and what to record about it."""

    name: str
    fn: Callable[..., dict[str, float]]
    label: str
    """Row label shown at the left of the panel."""
    signed: bool
    """True if the row draws a signed quantity on a diverging map centred on zero."""
    doc: str = ""


def diagnostic(*, name: str, label: str, signed: bool = False):
    """Register a panel row under the name cards refer to it by.

    Args:
        name: The vocabulary entry used in ``card.yaml``'s ``exemplars.diagnostics``.
        label: Human-readable row label for the figure.
        signed: Whether the row is drawn on a diverging map centred on zero.

    Returns:
        The undecorated function, so it stays directly callable and testable.
    """

    def register(fn: Callable[..., dict[str, float]]) -> Callable[..., dict[str, float]]:
        if name in DIAGNOSTICS:
            raise ValueError(f"diagnostic {name!r} is already registered")
        DIAGNOSTICS[name] = DiagnosticSpec(
            name=name, fn=fn, label=label, signed=signed, doc=fn.__doc__ or ""
        )
        return fn

    return register


@dataclass
class RowContext:
    """What a diagnostic needs to draw one row consistently across every column.

    Limits are computed once for the whole row and passed to each column rather than
    recomputed per panel. Per-panel autoscaling is the single most effective way to make a
    strong degradation look identical to the original, and it does it silently.
    """

    reference: np.ndarray
    """The undegraded field, for rows that draw a comparison."""
    grid: Any = None
    limits: tuple[float, float] | None = None
    extra: dict[str, Any] = dc_field(default_factory=dict)


# --------------------------------------------------------------------------------------
# Real-space rows
# --------------------------------------------------------------------------------------


@diagnostic(name="field", label="field")
def draw_field(ax, data: np.ndarray, ctx: RowContext) -> dict[str, float]:
    """The field itself, on limits shared with every other column."""
    style.show_field(ax, data, grid=ctx.grid, cmap="viridis",
                     vmin=ctx.limits[0], vmax=ctx.limits[1])
    values = np.asarray(data).ravel()
    return {"min": float(values.min()), "max": float(values.max()),
            "mean": float(values.mean()), "rms": float(np.sqrt((values**2).mean()))}


@diagnostic(name="difference", label="difference", signed=True)
def draw_difference(ax, data: np.ndarray, ctx: RowContext) -> dict[str, float]:
    """Degraded minus original, on a diverging map centred on zero.

    Limits come from the strongest severity so the weak column reads as legibly faint
    rather than being rescaled until it looks severe.
    """
    delta = np.asarray(data) - ctx.reference
    style.show_field(ax, delta, grid=ctx.grid, cmap="RdBu_r",
                     vmin=ctx.limits[0], vmax=ctx.limits[1])
    return {"max_abs": float(np.abs(delta).max()),
            "rms": float(np.sqrt((delta**2).mean())),
            "mean": float(delta.mean())}


@diagnostic(name="lineout", label="lineout")
def draw_lineout(ax, data: np.ndarray, ctx: RowContext) -> dict[str, float]:
    """A one-dimensional cut through the middle, with the original behind it in grey.

    The row that shows what happens to a sharp front, which a colour map flattens.
    """
    array = np.asarray(data)
    array = array[0] if array.ndim == 3 else array
    reference = ctx.reference[0] if ctx.reference.ndim == 3 else ctx.reference
    row = array.shape[1] // 2
    ax.plot(reference[:, row], color="0.7", lw=1.0)
    ax.plot(array[:, row], color=style.okabe("blue"), lw=1.0)
    ax.set_ylim(ctx.limits)
    cut = array[:, row]
    return {"max": float(cut.max()), "min": float(cut.min()),
            "max_gradient": float(np.abs(np.diff(cut)).max())}


# --------------------------------------------------------------------------------------
# Spectral rows
# --------------------------------------------------------------------------------------


def _radial_spectrum(data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Radially averaged power spectrum, using the repository's one |k| definition."""
    array = np.asarray(data)
    array = array[0] if array.ndim == 3 else array
    power = np.abs(np.fft.fftn(array)) ** 2
    k = wavenumber_magnitude(array.shape)
    shells = np.rint(k).astype(int)
    n = shells.max() + 1
    total = np.bincount(shells.ravel(), weights=power.ravel(), minlength=n)
    count = np.bincount(shells.ravel(), minlength=n)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(count > 0, total / np.maximum(count, 1), np.nan)
    return np.arange(n), mean


@diagnostic(name="radial_spectrum", label="radial spectrum")
def draw_radial_spectrum(ax, data: np.ndarray, ctx: RowContext) -> dict[str, float]:
    """Radially averaged power spectrum, log-log, with the original overplotted in grey.

    The reference curve is drawn in every column so a reader can see where the degraded
    field departs from it without holding two panels in mind at once.
    """
    k_ref, p_ref = _radial_spectrum(ctx.reference)
    k, power = _radial_spectrum(data)
    ax.loglog(k_ref[1:], p_ref[1:], color="0.7", lw=1.0)
    ax.loglog(k[1:], power[1:], color=style.okabe("blue"), lw=1.0)
    nyquist = ctx.extra.get("nyquist")
    if nyquist:
        ax.axvline(nyquist, color="0.5", ls=":", lw=0.8)
    ax.set_ylim(ctx.limits)

    # The wavenumber where this field has lost a tenth of the reference's power: a
    # single number standing for "where the curve peels away", for the fingerprint.
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.where(p_ref[1:] > 0, power[1:] / p_ref[1:], np.nan)
    departed = np.flatnonzero(np.isfinite(ratio) & (ratio < 0.9))
    total = float(np.nansum(power[1:]))
    reference_total = float(np.nansum(p_ref[1:]))
    return {
        "departure_wavenumber": float(k[1:][departed[0]]) if departed.size else float("nan"),
        "power_retained": total / reference_total if reference_total > 0 else float("nan"),
    }


@diagnostic(name="spectral_phase", label="phase difference", signed=True)
def draw_spectral_phase(ax, data: np.ndarray, ctx: RowContext) -> dict[str, float]:
    """Phase difference from the original, mode by mode.

    The row for degradations that move structure without changing how much of it there
    is. A translation leaves every amplitude untouched and shows up only here.
    """
    array = np.asarray(data)
    array = array[0] if array.ndim == 3 else array
    reference = ctx.reference[0] if ctx.reference.ndim == 3 else ctx.reference
    delta = np.angle(np.fft.fftn(array) * np.conj(np.fft.fftn(reference)))
    style.show_field(ax, np.fft.fftshift(delta), cmap="twilight_shifted",
                     vmin=-np.pi, vmax=np.pi)
    weight = np.abs(np.fft.fftn(reference)) ** 2
    weighted = float(np.sum(np.abs(delta) * weight) / max(weight.sum(), 1e-300))
    return {"mean_abs_phase_shift": float(np.abs(delta).mean()),
            "energy_weighted_phase_shift": weighted}


# --------------------------------------------------------------------------------------
# Distribution rows
# --------------------------------------------------------------------------------------


@diagnostic(name="pdf", label="value distribution")
def draw_pdf(ax, data: np.ndarray, ctx: RowContext) -> dict[str, float]:
    """Single-point distribution of values, with the original behind it in grey.

    The row that shows noise and gain errors, which move the distribution without moving
    anything in space.
    """
    values = np.asarray(data).ravel()
    reference = np.asarray(ctx.reference).ravel()
    bins = np.linspace(ctx.limits[0], ctx.limits[1], 61)
    ax.hist(reference, bins=bins, color="0.8", histtype="stepfilled")
    ax.hist(values, bins=bins, color=style.okabe("blue"), histtype="step", lw=1.0)
    ax.set_yscale("log")
    centred = values - values.mean()
    variance = float((centred**2).mean())
    return {
        "mean": float(values.mean()),
        "std": float(np.sqrt(variance)),
        "flatness": float((centred**4).mean() / variance**2) if variance > 0 else float("nan"),
    }


@diagnostic(name="autocorrelation", label="autocorrelation")
def draw_autocorrelation(ax, data: np.ndarray, ctx: RowContext) -> dict[str, float]:
    """Two-point correlation against separation, with the original in grey.

    The row that shows a change in the size of structures rather than their amplitude.
    """
    def profile(array: np.ndarray) -> np.ndarray:
        array = array[0] if array.ndim == 3 else array
        centred = array - array.mean()
        power = np.abs(np.fft.fftn(centred)) ** 2
        correlation = np.real(np.fft.ifftn(power))
        correlation /= correlation.flat[0] if correlation.flat[0] != 0 else 1.0
        return correlation[: array.shape[0] // 2, 0]

    reference = profile(np.asarray(ctx.reference))
    current = profile(np.asarray(data))
    ax.plot(reference, color="0.7", lw=1.0)
    ax.plot(current, color=style.okabe("blue"), lw=1.0)
    ax.set_ylim(-0.5, 1.05)
    below = np.flatnonzero(current < 1.0 / np.e)
    return {"correlation_length": float(below[0]) if below.size else float("nan")}
