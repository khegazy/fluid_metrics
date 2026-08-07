"""Turn a config ladder into concrete rungs, and apply them to frames.

A **ladder entry** (its label) is the unit of rank correlation, not the family. The config
keys the ladder by an arbitrary instance label with ``op`` naming the registry entry, so
the same operator can appear twice with different options -- ``translate_x`` and
``translate_y`` become two independent monotone axes that still plot in one colour::

    ladder:
      gaussian_blur:      {severities: [0.5, 1, 2, 4, 8]}
      translate_x:        {op: translate, severities: [1, 2, 4], options: {axis: x}}
      translate_y:        {op: translate, severities: [1, 2, 4], options: {axis: y}}
      lowpass_ideal:      {severities: [64, 32, 16, 8]}   # auto-sorted; direction=decreasing
      gaussian_impostor:  {severities: [0]}               # ordinal=False, excluded from rho
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field as dc_field
from typing import Any

import numpy as np

from degradations import registry as deg_registry
from degradations.registry import DegradationSpec

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
                    severity_name=spec.severity_name,
                    severity_units=spec.severity_units,
                    ordinal=spec.ordinal,
                    stochastic=spec.stochastic,
                    options=options,
                )
            )
    return rungs


def apply_rung(
    rung: Rung,
    frame: Frame,
    fields: Sequence[str],
    *,
    seed: int,
    reference_rms: Mapping[str, float] | None = None,
) -> dict[str, np.ndarray]:
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

    Returns:
        Canonical name -> degraded array, same shapes as the input.
    """
    if rung.is_reference:
        return {name: frame.fields[name] for name in fields}

    spec = deg_registry.get(rung.op)
    out: dict[str, np.ndarray] = {}
    for name in fields:
        source = frame.fields[name]
        if spec.fields != ("*",) and name not in spec.fields:
            out[name] = source
            continue
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
        result = np.asarray(spec.fn(source, rung.severity, **kwargs), dtype=np.float64)
        if result.shape != source.shape:
            raise ValueError(
                f"{rung.op} changed the shape of {name}: {source.shape} -> {result.shape}"
            )
        out[name] = result
    return out


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
