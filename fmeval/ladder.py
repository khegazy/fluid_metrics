"""Turn a config ladder into concrete rungs, and apply them to frames.

A **ladder entry** (its label) is the unit of rank correlation, not the family. The config
keys the ladder by an arbitrary instance label with ``op`` naming the registry entry, so
the same operator can appear twice with different options -- ``translate_x`` and
``translate_y`` become two independent monotone axes that still plot in one colour::

    ladder:
      gaussian_blur:      {severities: [0.5, 1, 2, 4, 8]}
      translate_x:        {op: translate, severities: [1, 2, 4], options: {axis: x}}
      translate_y:        {op: translate, severities: [1, 2, 4], options: {axis: y}}
      lowpass_ideal:      {severities: [0.05, 0.15, 0.3]} # calibrated: energy fraction
      gaussian_impostor:  {severities: [0]}               # ordinal=False, excluded from rho
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field as dc_field
from typing import Any

import numpy as np

from degradations import registry as deg_registry
from degradations.registry import DegradationSpec

from .calibration import Calibration, FieldCalibration
from .context import FieldContext, derive_rng, fluctuation_rms
from .data.base import Frame


@dataclass(frozen=True)
class Rung:
    """One point on one ladder axis."""

    label: str
    """The ladder-entry label, e.g. ``translate_x``. The unit of rank correlation."""
    op: str
    """Registry name of the operator, e.g. ``translate``."""
    family: str
    level: int
    """Ordinal within this axis; 0 is always the clean/mildest end."""
    severity: float
    """As written in config. For a calibrated operator this is *nominal* -- a fraction of
    energy or of the characteristic scale -- and :func:`resolve_severity` turns it into the
    absolute value actually applied, which differs per field."""
    calibration: str | None
    severity_name: str
    severity_units: str
    ordinal: bool
    stochastic: bool
    options: dict[str, Any] = dc_field(default_factory=dict)

    @property
    def variant_label(self) -> str:
        """Stable identifier for this rung, used in filenames and result rows."""
        if self.op == "identity":
            return "reference"
        return f"{self.label}_l{self.level}"

    @property
    def is_reference(self) -> bool:
        return self.op == "identity"


REFERENCE_RUNG = Rung(
    label="identity",
    op="identity",
    family="identity",
    level=0,
    severity=0.0,
    calibration=None,
    severity_name="n/a",
    severity_units="",
    ordinal=True,
    stochastic=False,
)


def build_ladder(
    ladder_cfg: Mapping[str, Mapping[str, Any]],
    *,
    include_reference: bool = True,
    only: Sequence[str] = (),
    skip: Sequence[str] = (),
) -> list[Rung]:
    """Expand a config ladder into a flat, ordered list of rungs.

    Args:
        ladder_cfg: Mapping of entry label -> ``{op?, severities, options?, enabled?}``.
            ``op`` defaults to the label.
        include_reference: Prepend the identity rung (level 0 of the whole ladder).
        only: If non-empty, keep only these entry labels.
        skip: Entry labels to drop, applied after ``only``.

    Returns:
        Rungs in config order, severities within each entry sorted into
        increasing-damage order and numbered from level 1.

    Raises:
        KeyError: On an unknown operator name.
        ValueError: On a malformed entry.
    """
    rungs: list[Rung] = []
    if include_reference:
        rungs.append(REFERENCE_RUNG)

    for label, raw in ladder_cfg.items():
        entry = dict(raw or {})
        if not entry.pop("enabled", True):
            continue
        if only and label not in only:
            continue
        if label in skip:
            continue

        op_name = entry.pop("op", label)
        spec = deg_registry.get(op_name)
        severities = entry.pop("severities", None)
        if severities is None:
            raise ValueError(f"ladder entry {label!r} has no 'severities'")
        options = dict(spec.defaults)
        options.update(entry.pop("options", None) or {})
        if entry:
            raise ValueError(
                f"ladder entry {label!r} has unexpected keys {sorted(entry)}; "
                "expected op / severities / options / enabled"
            )

        # Sorted by increasing damage, so a decreasing-direction list written in any
        # order still gets correct ordinal levels. Getting this wrong inverts a Spearman.
        for level, severity in enumerate(spec.sort_severities(severities), start=1):
            rungs.append(
                Rung(
                    label=label,
                    op=op_name,
                    family=spec.family,
                    level=level,
                    severity=float(severity),
                    calibration=spec.calibration,
                    severity_name=spec.severity_name,
                    severity_units=spec.severity_units,
                    ordinal=spec.ordinal,
                    stochastic=spec.stochastic,
                    options=options,
                )
            )
    return rungs


def resolve_severity(rung: Rung, field: str,
                    calibration: Calibration | None) -> float:
    """Turn a nominal severity into the absolute value to apply to ``field``.

    Absolute operators pass straight through. A calibrated one is resolved against the
    field's measured spectrum, so the same config number destroys the same fraction of
    structure on a smooth field and a broadband one.

    Raises:
        KeyError: If the operator needs a calibration and none was measured for the field.
            Failing is deliberate: silently falling back to the nominal value would apply an
            energy fraction as though it were a wavenumber, which is meaningless and would
            look like a plausible result.
    """
    if rung.calibration is None:
        return rung.severity
    if calibration is None or field not in calibration:
        raise KeyError(
            f"{rung.op!r} declares calibration={rung.calibration!r} but no calibration was "
            f"measured for field {field!r}. Its severity is a relative quantity and cannot "
            "be applied as an absolute one."
        )
    measured: FieldCalibration = calibration[field]
    if rung.calibration in ("energy_above", "energy_below"):
        side = "above" if rung.calibration == "energy_above" else "below"
        return measured.cutoff_removing_energy(rung.severity, side)
    if rung.calibration == "scale":
        return measured.length_for_scale_fraction(rung.severity)
    raise KeyError(f"unknown calibration kind {rung.calibration!r}")


def realised_severities(
    rungs: Sequence[Rung], field: str, calibration: Calibration | None
) -> dict[str, list[float]]:
    """Resolved severity of every rung of every axis, for one field, in level order."""
    out: dict[str, list[float]] = {}
    for rung in rungs:
        if rung.is_reference:
            continue
        out.setdefault(rung.label, []).append(resolve_severity(rung, field, calibration))
    return out


def degenerate_rungs(
    rungs: Sequence[Rung], field: str, calibration: Calibration | None
) -> dict[str, list[int]]:
    """Levels whose resolved severity duplicates a milder rung on the same axis.

    A calibrated severity is a real number but most operators act on a quantised one -- a sharp
    filter zeroes whole wavenumber shells, and a windowed kernel takes an odd number of cells --
    so two different nominal severities can resolve to the *same experiment*. That is not a
    tuning mistake; it is a limit of the field. Density keeps 69% of its fluctuation energy in
    the single shell k=1, so no cutoff ladder on density has more than about two distinct rungs,
    however the config is written.

    Reporting such a rung as a fourth point would inflate every axis statistic: the rank
    correlation would score a tie as agreement and the adjacent-rung separability would compare a
    distribution against itself. They are therefore identified here, recorded per row, and
    excluded from the acceptance statistics.

    Returns:
        Mapping of axis label -> the levels (1-based) that duplicate an earlier one.
    """
    quantised = {}
    for rung in rungs:
        if rung.is_reference or rung.calibration is None:
            continue
        spec = deg_registry.get(rung.op)
        severity = resolve_severity(rung, field, calibration)
        quantised.setdefault(rung.label, []).append(
            (rung.level, spec.quantise_severity(severity))
        )

    out: dict[str, list[int]] = {}
    for label, pairs in quantised.items():
        seen: set[float] = set()
        dupes = []
        for level, value in sorted(pairs):
            if value in seen:
                dupes.append(level)
            seen.add(value)
        if dupes:
            out[label] = dupes
    return out


def apply_rung(
    rung: Rung,
    frame: Frame,
    fields: Sequence[str],
    *,
    seed: int,
    reference_rms: Mapping[str, float] | None = None,
    calibration: Calibration | None = None,
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    """Apply one rung to the requested fields of a frame.

    Each field gets its own RNG derived from ``(seed, label, frame_index, field)``, so
    stochastic operators draw independently per field while deterministic ones stay
    automatically consistent, and nothing depends on iteration order.

    Args:
        rung: The rung to apply.
        frame: Source frame; its arrays are not modified.
        fields: Which fields to degrade.
        seed: Run-level seed.
        reference_rms: Precomputed fluctuation RMS per field, so noise amplitudes are
            relative to the *reference* rather than to whatever the previous rung left.
        calibration: Measured field properties, needed by any operator declaring a
            ``calibration``.

    Returns:
        ``(degraded, resolved, unchanged)`` -- the degraded arrays; the absolute severity
        actually applied to each field, which differs between fields for a calibrated operator
        and is recorded on every result row; and the fields the operator left bitwise identical
        to the reference.

        ``unchanged`` exists because a calibrated severity can resolve to a value at which the
        operator does nothing, and such a rung is not an experiment. Measured: the mildest
        high-pass rung asks to remove 20% of the density energy, but 69% of it sits in the single
        shell k=1, so the cutoff floors at k=1 and -- with the k=0 mean deliberately preserved --
        the filter passes every mode. Left unflagged it contributes an exactly-zero damage that
        makes the axis appear to span eleven orders of magnitude.
    """
    if rung.is_reference:
        return {name: frame.fields[name] for name in fields}, {}, set()

    spec = deg_registry.get(rung.op)
    out: dict[str, np.ndarray] = {}
    resolved: dict[str, float] = {}
    unchanged: set[str] = set()
    for name in fields:
        source = frame.fields[name]
        if spec.fields != ("*",) and name not in spec.fields:
            out[name] = source
            continue
        severity = resolve_severity(rung, name, calibration)
        resolved[name] = severity
        rms = (
            reference_rms[name]
            if reference_rms is not None and name in reference_rms
            else fluctuation_rms(source)
        )
        ctx = FieldContext(
            field=name,
            grid=frame.grid,
            frame_index=frame.index,
            time=frame.time,
            fluctuation_rms=rms,
            rng=derive_rng(seed, rung.variant_label, frame.index, name),
        )
        kwargs = dict(rung.options)
        if spec.takes_ctx:
            kwargs["ctx"] = ctx
        result = np.asarray(spec.fn(source, severity, **kwargs), dtype=np.float64)
        if result.shape != source.shape:
            raise ValueError(
                f"{rung.op} changed the shape of {name}: {source.shape} -> {result.shape}"
            )
        out[name] = result
        if _is_noop(source, result, rms):
            unchanged.add(name)
    return out, resolved, unchanged


#: Relative change below which an operator is treated as having done nothing. Bitwise equality
#: is too strict: every spectral operator makes an FFT round trip, so a filter whose transfer
#: function is identically one still returns an array that differs from its input in the last
#: bits. Round-trip error is of order 1e-16 relative while the mildest genuine rung measured here
#: changes the field by about 2e-2 of its fluctuation RMS, so any threshold in between separates
#: them cleanly and 1e-8 is nowhere near either.
NOOP_RELATIVE_TOLERANCE = 1e-8


def _is_noop(source: np.ndarray, result: np.ndarray, rms: float) -> bool:
    """Whether an operator changed the field by more than round-off."""
    if rms <= 0:
        return bool(np.array_equal(source, result))
    change = float(np.sqrt(np.mean((result - source) ** 2)))
    return change < NOOP_RELATIVE_TOLERANCE * rms


def reference_fluctuation_rms(frame: Frame, fields: Sequence[str]) -> dict[str, float]:
    """Fluctuation RMS of each reference field, for scaling relative severities."""
    return {name: fluctuation_rms(frame.fields[name]) for name in fields}


def ladder_axes(rungs: Sequence[Rung]) -> list[str]:
    """Distinct ladder-entry labels, excluding the reference. The Spearman units."""
    seen: list[str] = []
    for r in rungs:
        if not r.is_reference and r.label not in seen:
            seen.append(r.label)
    return seen


def ordinal_axes(rungs: Sequence[Rung]) -> list[str]:
    """Ladder axes that participate in rank correlation (the IN-4 canary does not)."""
    return [
        label
        for label in ladder_axes(rungs)
        if next(r for r in rungs if r.label == label).ordinal
    ]


def spec_for(rung: Rung) -> DegradationSpec:
    """The registry spec behind a rung."""
    return deg_registry.get(rung.op)
