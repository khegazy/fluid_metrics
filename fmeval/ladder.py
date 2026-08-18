"""Turn a config ladder into concrete severity levels, and apply them to frames.

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
class SeverityLevel:
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
        """Stable identifier for this severity level, used in filenames and result rows."""
        if self.op == "identity":
            return "reference"
        return f"{self.label}_l{self.level}"

    @property
    def is_reference(self) -> bool:
        return self.op == "identity"


REFERENCE_LEVEL = SeverityLevel(
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
) -> list[SeverityLevel]:
    """Expand a config ladder into a flat, ordered list of severity levels.

    Args:
        ladder_cfg: Mapping of entry label -> ``{op?, severities, options?, enabled?}``.
            ``op`` defaults to the label.
        include_reference: Prepend the identity severity level (level 0 of the whole ladder).
        only: If non-empty, keep only these entry labels.
        skip: Entry labels to drop, applied after ``only``.

    Returns:
        Severity levels in config order, severities within each entry sorted into
        increasing-damage order and numbered from level 1.

    Raises:
        KeyError: On an unknown operator name.
        ValueError: On a malformed entry.
    """
    severity_levels: list[SeverityLevel] = []
    if include_reference:
        severity_levels.append(REFERENCE_LEVEL)

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
            severity_levels.append(
                SeverityLevel(
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
    return severity_levels


def resolve_severity(severity_level: SeverityLevel, field: str,
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
    if severity_level.calibration is None:
        return severity_level.severity
    if calibration is None or field not in calibration:
        raise KeyError(
            f"{severity_level.op!r} declares calibration={severity_level.calibration!r} but no calibration was "
            f"measured for field {field!r}. Its severity is a relative quantity and cannot "
            "be applied as an absolute one."
        )
    measured: FieldCalibration = calibration[field]
    if severity_level.calibration in ("energy_above", "energy_below"):
        side = "above" if severity_level.calibration == "energy_above" else "below"
        return measured.cutoff_removing_energy(severity_level.severity, side)
    if severity_level.calibration == "scale":
        return measured.length_for_scale_fraction(severity_level.severity)
    raise KeyError(f"unknown calibration kind {severity_level.calibration!r}")


@dataclass(frozen=True)
class SeverityLevelApplication:
    """The result of applying one severity level to one frame, with what it measurably did.

    A severity level's *requested* severity and its *realised* effect are different numbers, and on a field
    whose energy is concentrated in a few modes they differ a lot: a sharp filter must land on an
    available set of modes, so the nearest cutoff to a request can remove far more or far less than
    was asked for. Measured on density, whose fluctuation energy is 69% in the four diagonal modes
    at |k| = sqrt(2), the mildest high-pass severity level removes 3e-5 of the energy and the next removes
    0.70. Reporting only the request would leave a reader unable to tell those apart, so the effect
    is measured per field and carried on every result row.
    """

    fields: dict[str, np.ndarray]
    """The degraded arrays."""
    resolved: dict[str, float]
    """Absolute severity actually applied, per field. Differs between fields when calibrated."""
    unchanged: set[str]
    """Fields the operator left alone to within round-off, so the severity level is not an experiment."""
    energy_removed: dict[str, float]
    """Fraction of the reference's fluctuation energy the operator eliminated.

    ``1 - var(degraded) / var(reference)``. For a filter this is exactly the energy removed. It is
    near zero for an operator that relocates rather than removes -- a translation -- and negative
    for one that adds energy, such as noise; both are informative rather than defects, and are the
    reason this is reported next to the severity instead of being inferred from it.
    """
    energy_changed: dict[str, float]
    """Fraction of the reference's fluctuation energy sitting in the difference field.

    ``mean((degraded - reference)^2) / var(reference)``. Defined for every operator, including
    those that move or add energy rather than removing it, so it is the one number comparable
    across every axis.
    """


@dataclass(frozen=True)
class SeverityLevelApplication:
    """The result of applying one severity level to one frame, with what it measurably did.

    A severity level's *requested* severity and its *realised* effect are different numbers, and on a field
    with a steep spectrum they differ a lot: a sharp high-pass asked to remove 45% of the density
    energy resolves to the lowest available cutoff and removes either none of it or 69%, because
    69% sits in that one wavenumber shell. Reporting only the request would leave a reader unable
    to tell those apart, so the effect is measured per field and carried on every result row.
    """

    fields: dict[str, np.ndarray]
    """The degraded arrays."""
    resolved: dict[str, float]
    """Absolute severity actually applied, per field. Differs between fields when calibrated."""
    unchanged: set[str]
    """Fields the operator left alone to within round-off, so the severity level is not an experiment."""
    energy_removed: dict[str, float]
    """Fraction of the reference's fluctuation energy the operator eliminated.

    ``1 - var(degraded) / var(reference)``. For a filter this is exactly the energy removed. It is
    near zero for an operator that relocates rather than removes -- a translation -- and negative
    for one that adds energy, such as noise; both are informative rather than defects, and are the
    reason this is reported next to the severity instead of being inferred from it.
    """
    energy_changed: dict[str, float]
    """Fraction of the reference's fluctuation energy sitting in the difference field.

    ``mean((degraded - reference)^2) / var(reference)``. Defined for every operator, including
    those that move or add energy rather than removing it, so it is the one number comparable
    across every axis.
    """


def apply_severity_level(
    severity_level: SeverityLevel,
    frame: Frame,
    fields: Sequence[str],
    *,
    seed: int,
    reference_rms: Mapping[str, float] | None = None,
    calibration: Calibration | None = None,
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    """Apply one severity level to the requested fields of a frame.

    Each field gets its own RNG derived from ``(seed, label, frame_index, field)``, so
    stochastic operators draw independently per field while deterministic ones stay
    automatically consistent, and nothing depends on iteration order.

    Args:
        severity level: The severity level to apply.
        frame: Source frame; its arrays are not modified.
        fields: Which fields to degrade.
        seed: Run-level seed.
        reference_rms: Precomputed fluctuation RMS per field, so noise amplitudes are
            relative to the *reference* rather than to whatever the previous severity level left.
        calibration: Measured field properties, needed by any operator declaring a
            ``calibration``.

    Returns:
        A :class:`SeverityLevelApplication`: the degraded arrays, the absolute severity applied to each
        field, the fields left untouched, and how much of each field's fluctuation energy the
        operator removed and changed.

        ``unchanged`` exists because a calibrated severity can resolve to a value at which the
        operator does nothing, and such a severity level is not an experiment. Measured: a mild high-pass
        request on density floors at the lowest usable cutoff |k| = 1, and since the axis modes
        there hold only 3e-5 of the energy -- with the k=0 mean deliberately preserved -- the filter
        passes essentially everything. Left unflagged such a severity level contributes an exactly-zero damage
        that makes the axis appear to span eleven orders of magnitude.
    """
    if severity_level.is_reference:
        return SeverityLevelApplication(
            fields={name: frame.fields[name] for name in fields},
            resolved={}, unchanged=set(),
            energy_removed={name: 0.0 for name in fields},
            energy_changed={name: 0.0 for name in fields},
        )

    spec = deg_registry.get(severity_level.op)
    out: dict[str, np.ndarray] = {}
    resolved: dict[str, float] = {}
    unchanged: set[str] = set()
    removed: dict[str, float] = {}
    changed: dict[str, float] = {}

    if spec.whole_frame:
        out = _apply_whole_frame(spec, severity_level, frame, fields, seed=seed,
                                 reference_rms=reference_rms, calibration=calibration,
                                 resolved=resolved)
    for name in fields:
        source = frame.fields[name]
        if spec.whole_frame:
            # Already produced above, in one call over the whole frame. Only the per-field
            # bookkeeping below still has to happen.
            rms = (
                reference_rms[name]
                if reference_rms is not None and name in reference_rms
                else fluctuation_rms(source)
            )
            if _is_noop(source, out[name], rms):
                unchanged.add(name)
            removed[name], changed[name] = _energy_effect(source, out[name])
            continue
        if spec.fields != ("*",) and name not in spec.fields:
            out[name] = source
            continue
        severity = resolve_severity(severity_level, name, calibration)
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
            rng=derive_rng(seed, severity_level.variant_label, frame.index, name),
        )
        kwargs = dict(severity_level.options)
        if spec.takes_ctx:
            kwargs["ctx"] = ctx
        result = np.asarray(spec.fn(source, severity, **kwargs), dtype=np.float64)
        if result.shape != source.shape:
            raise ValueError(
                f"{severity_level.op} changed the shape of {name}: {source.shape} -> {result.shape}"
            )
        out[name] = result
        if _is_noop(source, result, rms):
            unchanged.add(name)
        removed[name], changed[name] = _energy_effect(source, result)
    return SeverityLevelApplication(fields=out, resolved=resolved, unchanged=unchanged,
                           energy_removed=removed, energy_changed=changed)


#: Relative change below which an operator is treated as having done nothing. Bitwise equality
#: is too strict: every spectral operator makes an FFT round trip, so a filter whose transfer
#: function is identically one still returns an array that differs from its input in the last
#: bits. Round-trip error is of order 1e-16 relative while the mildest genuine severity level measured here
#: changes the field by about 2e-2 of its fluctuation RMS, so any threshold in between separates
#: them cleanly and 1e-8 is nowhere near either.
NOOP_RELATIVE_TOLERANCE = 1e-8


def _apply_whole_frame(
    spec: DegradationSpec,
    severity_level: SeverityLevel,
    frame: Frame,
    fields: Sequence[str],
    *,
    seed: int,
    reference_rms: Mapping[str, float] | None,
    calibration: Calibration | None,
    resolved: dict[str, float],
) -> dict[str, np.ndarray]:
    """Apply an operator that declared ``whole_frame=True``, in one call over every field.

    The rare operator that genuinely needs cross-field access -- a Leray projection, a rotation
    that must rotate the velocity *components* and not merely resample the grid, a
    density-weighted remap -- cannot work one array at a time. It receives the field mapping and
    returns one, and its context describes the frame rather than any single field.

    This was declared, defaulted and documented in two places for a long time while
    :func:`apply_severity_level` never read it, so such an operator would have received a bare array where
    it expected a mapping and failed with a message pointing at numpy rather than at the ignored
    declaration.

    Args:
        resolved: Filled in with the severity applied to each field, in place.

    Raises:
        TypeError: If the operator does not return a mapping.
        KeyError: If it drops a requested field.
        ValueError: If it changes a field's shape.
    """
    severity = resolve_severity(severity_level, fields[0], calibration) if fields else severity_level.severity
    for name in fields:
        resolved[name] = resolve_severity(severity_level, name, calibration)
    if len({resolved[name] for name in fields}) > 1:
        raise ValueError(
            f"{severity_level.op!r} declares whole_frame=True and calibration={severity_level.calibration!r}, but a "
            "calibrated severity resolves per field and a whole-frame operator gets one call for "
            "all of them. Use per-field application, or an absolute severity."
        )

    ctx = FieldContext(
        field=",".join(fields),      # the operator sees every field, so no single name fits
        grid=frame.grid,
        frame_index=frame.index,
        time=frame.time,
        fluctuation_rms=float(np.mean([
            reference_rms[name] if reference_rms is not None and name in reference_rms
            else fluctuation_rms(frame.fields[name])
            for name in fields
        ])) if fields else 0.0,
        rng=derive_rng(seed, severity_level.variant_label, frame.index, "*"),
    )
    kwargs = dict(severity_level.options)
    if spec.takes_ctx:
        kwargs["ctx"] = ctx

    source = {name: frame.fields[name] for name in fields}
    result = spec.fn(source, severity, **kwargs)
    if not isinstance(result, Mapping):
        raise TypeError(
            f"{severity_level.op!r} declares whole_frame=True so it must return a mapping of field name "
            f"to array, not {type(result).__name__}"
        )
    out: dict[str, np.ndarray] = {}
    for name in fields:
        if name not in result:
            raise KeyError(
                f"{severity_level.op!r} declares whole_frame=True and dropped field {name!r}; it must "
                f"return every field it was given ({sorted(fields)})"
            )
        array = np.asarray(result[name], dtype=np.float64)
        if array.shape != frame.fields[name].shape:
            raise ValueError(
                f"{severity_level.op} changed the shape of {name}: "
                f"{frame.fields[name].shape} -> {array.shape}"
            )
        out[name] = array
    return out


def _energy_effect(source: np.ndarray, result: np.ndarray) -> tuple[float, float]:
    """Fraction of the reference fluctuation energy removed, and the fraction changed.

    Both are about the *fluctuation*, with the spatial mean removed, for the same reason the
    calibration is: on density the mean is four orders of magnitude larger than the fluctuation, so
    energies computed about zero would say every operator changed nothing.
    """
    spatial = tuple(range(1, source.ndim))
    reference = source - source.mean(axis=spatial, keepdims=True)
    degraded = result - result.mean(axis=spatial, keepdims=True)
    total = float((reference**2).mean())
    if total <= 0:
        return 0.0, 0.0
    removed = 1.0 - float((degraded**2).mean()) / total
    changed = float(((result - source) ** 2).mean()) / total
    return removed, changed


def _is_noop(source: np.ndarray, result: np.ndarray, rms: float) -> bool:
    """Whether an operator changed the field by more than round-off."""
    if rms <= 0:
        return bool(np.array_equal(source, result))
    change = float(np.sqrt(np.mean((result - source) ** 2)))
    return change < NOOP_RELATIVE_TOLERANCE * rms


def reference_fluctuation_rms(frame: Frame, fields: Sequence[str]) -> dict[str, float]:
    """Fluctuation RMS of each reference field, for scaling relative severities."""
    return {name: fluctuation_rms(frame.fields[name]) for name in fields}


def ladder_axes(severity_levels: Sequence[SeverityLevel]) -> list[str]:
    """Distinct ladder-entry labels, excluding the reference. The Spearman units."""
    seen: list[str] = []
    for r in severity_levels:
        if not r.is_reference and r.label not in seen:
            seen.append(r.label)
    return seen


def ordinal_axes(severity_levels: Sequence[SeverityLevel]) -> list[str]:
    """Ladder axes that participate in rank correlation (the IN-4 canary does not)."""
    return [
        label
        for label in ladder_axes(severity_levels)
        if next(r for r in severity_levels if r.label == label).ordinal
    ]


def spec_for(severity_level: SeverityLevel) -> DegradationSpec:
    """The registry spec behind a severity level."""
    return deg_registry.get(severity_level.op)
