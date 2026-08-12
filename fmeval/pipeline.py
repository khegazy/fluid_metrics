"""The evaluation loop.

I/O costs about 10 ms per frame and a cheap metric costs 0.1 ms, so the loop order is
forced: **read each frame once, build every variant, then fan out over metrics.**

Order of operations within a frame:

1. Read the frame at its native resolution.
2. Remap onto the analysis grid (IN-2), recomputing derived fields there rather than
   averaging them.
3. Measure the reference fluctuation RMS, which sets the scale for relative severities.
4. Apply every ladder rung.
5. Evaluate every metric against every variant.

Remapping *before* degrading is deliberate. It keeps severity units meaningful: a one-cell
translation means one analysis-grid cell whatever the analysis resolution, rather than
silently becoming half a cell when the grid is halved. It also means derived fields are
recomputed exactly once per frame.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field as dc_field
from typing import Any

import numpy as np
import pandas as pd

from metrics.registry import MetricSpec

from .calibration import Calibration, calibrate
from .context import FieldContext, derive_rng
from .data.base import FIELDS, Frame, Trajectory, TimeSelection
from .ladder import Rung, apply_rung, reference_fluctuation_rms
from .remap import coarsen_factor, remap_frame

log = logging.getLogger(__name__)

#: Column order and dtype of the tidy result frame. Frozen: everything downstream --
#: every plot, table and analysis -- is a groupby on this one schema.
RESULT_DTYPES: dict[str, str] = {
    # provenance
    "dataset": "category",
    "dataset_family": "category",
    "complexity_rank": "Int16",
    "param_reynolds": "float64",
    "param_mach": "float64",
    "param_resolution": "Int32",
    "trajectory": "category",
    # position in the trajectory
    "frame_index": "int32",
    "time": "float64",
    # what was measured, on what
    "field": "category",
    "analysis_grid": "int32",
    "remap_op": "category",
    "metric": "category",
    "tracker_id": "category",
    "arity": "category",
    "higher_is_better": "bool",      # so the analysis orients its one-sided statistics by
                                     # the metric's own direction rather than assuming error
    # how the field was damaged
    "degradation": "category",       # the ladder-entry label: the unit of rank correlation
    "degradation_op": "category",    # the registry name behind it
    "degradation_family": "category",
    "level": "int16",
    "severity": "float64",           # the absolute value actually applied
    "severity_nominal": "float64",   # as written in config; differs for a calibrated operator
    "calibration": "category",
    "severity_degenerate": "bool",   # not a distinct experiment: repeats a milder rung, or
                                     # resolved to a severity at which the operator is a no-op
    "energy_removed": "float64",     # what the rung MEASURABLY did, as opposed to what it asked
    "energy_changed": "float64",     # for: both are fractions of the reference fluctuation
    "severity_name": "category",
    "variant_label": "category",
    # the number
    "component": "category",
    "value": "float64",
    "seed": "int64",
    "wall_time_s": "float64",
}


@dataclass(frozen=True)
class DatasetInfo:
    """Provenance and complexity metadata for one dataset, copied onto every row.

    ``family`` and ``rank`` are the warm start for comparing metrics across datasets of
    increasing physical complexity: without a declared ordering there is no axis to plot
    against, and back-filling it later across a dozen configs is tedious.
    """

    name: str
    trajectory: str = ""
    family: str = ""
    rank: int | None = None
    params: Mapping[str, float] = dc_field(default_factory=dict)

    def row(self) -> dict[str, Any]:
        return {
            "dataset": self.name,
            "dataset_family": self.family,
            "complexity_rank": self.rank,
            "param_reynolds": self.params.get("reynolds", np.nan),
            "param_mach": self.params.get("mach", np.nan),
            "param_resolution": self.params.get("resolution"),
            "trajectory": self.trajectory,
        }


@dataclass
class MapRequest:
    """Which pointwise metric maps to keep.

    Storing a map for every frame and variant would be gigabytes, so only the named
    combinations are retained -- enough for the figure, not for the whole run.
    """

    enabled: bool = True
    frames: Sequence[int] = (-1,)
    """Positions within the *selected* frames; -1 is the last one."""
    axes: Sequence[str] = ()
    """Ladder-entry labels to keep. Empty means all of them."""
    fields: Sequence[str] = ()
    """Fields to keep. Empty means all of them."""


@dataclass
class PipelineResult:
    """Everything one evaluation produced."""

    rows: pd.DataFrame
    maps: dict[str, np.ndarray] = dc_field(default_factory=dict)
    """``"<field>__<variant>__t<frame>"`` -> pointwise density, for ``error_maps.npz``."""
    n_frames: int = 0
    calibration: Calibration | None = None
    io_seconds: float = 0.0
    degrade_seconds: float = 0.0
    metric_seconds: float = 0.0


def _emit(
    spec: MetricSpec,
    field: str,
    frame: Frame,
    rung: Rung,
    info: DatasetInfo,
    analysis_grid: int,
    remap_op: str,
    seed: int,
    value: Any,
    wall: float,
    severity: float,
    degenerate: bool,
    energy_removed: float,
    energy_changed: float,
) -> list[dict[str, Any]]:
    """Expand one metric evaluation into result rows (several if it returns a vector)."""
    base = {
        **info.row(),
        "frame_index": frame.index,
        "time": frame.time,
        "field": field,
        "analysis_grid": analysis_grid,
        "remap_op": remap_op,
        "metric": spec.name,
        "tracker_id": spec.tracker_id or "",
        "arity": spec.arity,
        "higher_is_better": spec.higher_is_better,
        "degradation": rung.label,
        "degradation_op": rung.op,
        "degradation_family": rung.family,
        "level": rung.level,
        "severity": severity,
        "severity_nominal": rung.severity,
        "calibration": rung.calibration or "",
        "severity_degenerate": degenerate,
        "energy_removed": energy_removed,
        "energy_changed": energy_changed,
        "severity_name": rung.severity_name,
        "variant_label": rung.variant_label,
        "seed": seed,
        "wall_time_s": wall,
    }
    if spec.returns == "scalar":
        return [{**base, "component": "", "value": float(value)}]
    arr = np.asarray(value, dtype=np.float64).ravel()
    return [{**base, "component": str(i), "value": float(v)} for i, v in enumerate(arr)]


def _fields_for(spec: MetricSpec, available: Sequence[str]) -> list[str]:
    """Which of the available fields this metric accepts."""
    if spec.fields == ("*",):
        return list(available)
    return [f for f in available if f in spec.fields]


def _map_key(field: str, variant: str, frame_index: int) -> str:
    return f"{field}__{variant}__t{frame_index}"


def run(
    trajectory: Trajectory,
    metrics: Sequence[MetricSpec],
    rungs: Sequence[Rung],
    *,
    fields: Sequence[str],
    selection: TimeSelection | None = None,
    dataset: DatasetInfo,
    seed: int = 0,
    analysis_resolution: int | None = None,
    remap_method: str = "block_mean",
    maps: MapRequest | None = None,
    calibration_frames: int = 5,
) -> PipelineResult:
    """Evaluate every metric against every rung, over the selected frames.

    Args:
        trajectory: Source of frames.
        metrics: Metric specs to evaluate.
        rungs: The degradation ladder, including its reference rung.
        fields: Canonical field names to read. Metrics that do not accept a field skip it.
        selection: Which frames to evaluate. Defaults to all of them.
        dataset: Provenance copied onto every row.
        seed: Run seed; per-rung generators derive from it deterministically.
        analysis_resolution: IN-2 analysis grid, or None for the native resolution.
        remap_method: ``"block_mean"`` (conservative) or ``"subsample"``.
        maps: Which pointwise maps to retain.
        calibration_frames: How many frames to average the per-field spectral calibration
            over. Measured once and then held fixed for the whole run: re-measuring per frame
            would make the ladder itself drift as the flow evolves, so two frames would no
            longer be running the same experiment and the per-frame rank correlation would be
            comparing different ladders.

    Returns:
        A :class:`PipelineResult` whose ``rows`` follow :data:`RESULT_DTYPES` exactly.
    """
    selection = selection or TimeSelection()
    maps = maps or MapRequest(enabled=False)
    indices = selection.resolve(len(trajectory))
    if len(indices) == 0:
        raise ValueError("time selection is empty; check dataset.time.start / stop")

    factor = coarsen_factor(trajectory.grid, analysis_resolution)
    grid_size = trajectory.grid.shape[0] // factor
    keep_frames = _map_frames(maps, indices)

    expensive = [m.name for m in metrics if m.cost == "expensive"]
    if expensive and len(indices) > 500:
        log.warning(
            "%d frames x expensive metric(s) %s: consider raising dataset.time.reduction",
            len(indices), expensive,
        )

    calibration = _measure_calibration(
        trajectory, fields, indices, factor, remap_method, calibration_frames
    )

    probe = remap_frame(trajectory.frame(int(indices[0]), fields), factor,
                        method=remap_method)
    rungs = _runnable_rungs(rungs, probe, fields, seed=seed, calibration=calibration,
                            analysis_grid=grid_size)

    rows: list[dict[str, Any]] = []
    stored_maps: dict[str, np.ndarray] = {}
    t_io = t_deg = t_metric = 0.0

    for index in indices:
        t_read = time.perf_counter()
        frame = trajectory.frame(int(index), fields)
        t_io += time.perf_counter() - t_read

        t0 = time.perf_counter()
        frame = remap_frame(frame, factor, method=remap_method)
        available = [f for f in fields if f in frame.fields]
        ref_rms = reference_fluctuation_rms(frame, available)
        variants = {
            rung.variant_label: (rung, apply_rung(rung, frame, available, seed=seed,
                                                  reference_rms=ref_rms,
                                                  calibration=calibration))
            for rung in rungs
        }
        t_deg += time.perf_counter() - t0

        for spec in metrics:
            for field in _fields_for(spec, available):
                reference = frame.fields[field]
                n_channels = reference.shape[0]
                ctx = FieldContext(
                    field=field,
                    grid=frame.grid,
                    frame_index=frame.index,
                    time=frame.time,
                    fluctuation_rms=ref_rms[field],
                    rng=derive_rng(seed, "metric", frame.index, field),
                )
                kwargs = {"ctx": ctx} if spec.takes_ctx else {}

                for label, (rung, applied) in variants.items():
                    candidate = applied.fields[field]
                    severity = applied.resolved.get(field, rung.severity)
                    args = (
                        (reference, candidate) if spec.arity == "pairwise" else (candidate,)
                    )
                    t1 = time.perf_counter()
                    value = spec.fn(*args, **kwargs)
                    wall = time.perf_counter() - t1
                    t_metric += wall
                    rows.extend(
                        _emit(spec, field, frame, rung, dataset, grid_size,
                              remap_method, seed, value, wall, severity,
                              field in applied.unchanged and not rung.is_reference,
                              applied.energy_removed.get(field, float("nan")),
                              applied.energy_changed.get(field, float("nan")))
                    )

                    if (
                        maps.enabled
                        and spec.has_pointwise
                        and frame.index in keep_frames
                        and (not maps.axes or rung.label in maps.axes)
                        and (not maps.fields or field in maps.fields)
                    ):
                        m = spec.pointwise(*args, **kwargs)
                        stored_maps[_map_key(f"{spec.name}:{field}", label, frame.index)] = (
                            np.asarray(m, dtype=np.float64)
                        )

    # A metric may accept none of the available fields, which is a legitimate no-op
    # rather than an error -- but pd.DataFrame([]) has no columns to coerce.
    df = _coerce(pd.DataFrame(rows)) if rows else empty_results()
    df = _flag_repeated_rungs(df)
    return PipelineResult(
        rows=df,
        maps=stored_maps,
        n_frames=len(indices),
        calibration=calibration,
        io_seconds=t_io,
        degrade_seconds=t_deg,
        metric_seconds=t_metric,
    )


def _flag_repeated_rungs(df: pd.DataFrame) -> pd.DataFrame:
    """Mark rungs that turn out to be the same experiment as a milder rung, and log them.

    Detected by measurement rather than by declaration: two rungs whose severities resolve to the
    same quantised operation produce a bitwise identical field, hence an exactly equal
    ``energy_changed``. That is a stronger test than asking each operator to describe how it
    rounds, and it needs no such description -- it catches a sharp filter landing twice on the same
    set of modes, and a windowed kernel landing twice on the same odd width, alike.

    Such a rung is not padding, it is corruption: the rank correlation would score the tie as
    agreement and the adjacent-rung separability would compare a distribution against itself. It is
    also not a misconfiguration: 69% of density's fluctuation energy is in the four diagonal modes
    at |k| = sqrt(2), so the available cutoffs there are few and far apart and a sharp ladder has
    only a couple of distinct rungs however it is written.
    """
    if df.empty:
        return df

    repeated = pd.Series(False, index=df.index)
    for (field, axis), g in df[df["level"] > 0].groupby(
        ["field", "degradation"], observed=True
    ):
        seen: dict[float, int] = {}
        levels = []
        for level in sorted(g["level"].unique()):
            effect = float(g.loc[g["level"] == level, "energy_changed"].iloc[0])
            if effect in seen:
                repeated.loc[g.index[g["level"] == level]] = True
                levels.append((int(level), seen[effect]))
            else:
                seen[effect] = int(level)
        if levels:
            log.warning(
                "%s / %s: level(s) %s repeat the experiment of level(s) %s and are excluded "
                "from the acceptance statistics. The field's spectrum cannot resolve that many "
                "distinct rungs for this operator.",
                field, axis, [a for a, _ in levels], [b for _, b in levels],
            )

    _log_noop_rungs(df)          # before the merge, so the two reasons stay distinguishable
    df = df.copy()
    df["severity_degenerate"] = df["severity_degenerate"] | repeated
    return df


def _log_noop_rungs(df: pd.DataFrame) -> None:
    """Log rungs whose severity resolved to one at which the operator does nothing.

    Measured, not modelled: an operator is treated as having done nothing when it moved the field
    by less than round-off relative to its own fluctuation.
    """
    flagged = df[(df["level"] > 0) & df["severity_degenerate"]]
    for (field, axis), g in flagged.groupby(["field", "degradation"], observed=True):
        levels = sorted(int(level) for level in g["level"].unique())
        if levels:
            log.warning(
                "%s / %s: level(s) %s resolve to a severity at which the operator leaves the "
                "field unchanged, and are excluded from the acceptance statistics.",
                field, axis, levels,
            )


def _map_frames(maps: MapRequest, indices: np.ndarray) -> set[int]:
    """Resolve ``report.error_map.frames`` positions to trajectory frame indices.

    The positions are *within the selected frames*, so what is valid depends on
    ``dataset.time.reduction``, ``start``/``stop`` and the trajectory length. Raising the
    reduction shrinks the selection under a configured position, and indexing it raised
    ``IndexError: index 7 is out of bounds for axis 0 with size 4`` -- which names neither the
    setting that was out of range nor the one that shrank the selection. Negative positions count
    from the end, as elsewhere in numpy, and ``-1`` is the shipped default.

    Raises:
        ValueError: If a position is outside the selection.
    """
    if not (maps.enabled and maps.frames):
        return set()
    n = len(indices)
    out = set()
    for position in maps.frames:
        if not -n <= position < n:
            raise ValueError(
                f"report.error_map.frames contains {position}, which is outside the "
                f"{n} selected frame(s). The positions are counted within the selection, so "
                "they are bounded by dataset.time.reduction, start/stop and max_frames; "
                f"valid values here are {-n} to {n - 1}."
            )
        out.add(int(indices[position]))
    return out


def _runnable_rungs(
    rungs: Sequence[Rung],
    probe: Frame,
    fields: Sequence[str],
    *,
    seed: int,
    calibration: Calibration,
    analysis_grid: int,
) -> list[Rung]:
    """Drop rungs that cannot run on the analysis grid, before the frame loop starts.

    ``analysis_grid.resolution`` is one of the two documented size knobs, and turning it down
    far enough puts the configured ladder outside what the grid can support: the shipped ladder
    coarsens by up to 16, so at resolution 8 the run used to die partway through the first frame
    with ``ValueError: factor 16 does not divide grid (8, 8)`` -- an error naming the operator
    but not the knob that caused it, raised after the I/O for that frame had been paid. On a long
    trajectory that is a slow way to learn about a typo.

    The check is a trial application on one already-remapped frame, so it needs no per-operator
    declaration of what it can support and stays correct as operators are added. Rungs that fail
    are dropped with a warning naming the knob, and the run proceeds on the rest: an unsupported
    rung is one missing experiment, not a reason to discard the others.

    Raises:
        ValueError: If no rung survives, since there is then nothing to measure.
    """
    keep: list[Rung] = []
    for rung in rungs:
        try:
            apply_rung(rung, probe, fields, seed=seed, calibration=calibration)
        except Exception as exc:  # noqa: BLE001 - any failure means the rung cannot run here
            log.warning(
                "dropping %s level %d (%s = %g): it cannot run on the %d-cell analysis grid "
                "(%s). Raise analysis_grid.resolution or lower this severity.",
                rung.label, rung.level, rung.severity_name, rung.severity,
                analysis_grid, exc,
            )
            continue
        keep.append(rung)

    if not keep:
        raise ValueError(
            f"no ladder rung can run on the {analysis_grid}-cell analysis grid; every "
            "configured severity was rejected. Raise analysis_grid.resolution."
        )
    return keep


def _measure_calibration(
    trajectory: Trajectory,
    fields: Sequence[str],
    indices: np.ndarray,
    factor: int,
    remap_method: str,
    n_sample: int,
) -> Calibration:
    """Measure each field's spectral properties on the analysis grid, once.

    Sampled evenly across the selected frames rather than from the start, so a trajectory
    whose spectrum evolves is represented rather than characterised by its beginning.
    """
    if n_sample < 1:
        return Calibration()
    chosen = indices[np.unique(np.linspace(0, len(indices) - 1, n_sample).astype(int))]

    frames_by_field: dict[str, list[np.ndarray]] = {f: [] for f in fields}
    grid = None
    for index in chosen:
        frame = remap_frame(trajectory.frame(int(index), fields), factor,
                            method=remap_method)
        grid = frame.grid
        for name, array in frame.fields.items():
            frames_by_field.setdefault(name, []).append(array)

    if grid is None:  # pragma: no cover - indices is non-empty by this point
        return Calibration()
    result = calibrate(frames_by_field, grid, fields)
    for entry in result.summary():
        log.info(
            "calibration %s: scale %.1f cells (spread %.0f%%), k(50/90/99%%) = %d/%d/%d",
            entry["field"], entry["characteristic_scale"], 100 * entry["scale_spread"],
            entry["k_energy_50"], entry["k_energy_90"], entry["k_energy_99"],
        )
    return result


def _coerce(df: pd.DataFrame) -> pd.DataFrame:
    """Put the frame into the frozen schema: exact columns, exact order, exact dtypes."""
    missing = set(RESULT_DTYPES) - set(df.columns)
    if missing:
        raise ValueError(f"result frame is missing columns: {sorted(missing)}")
    extra = set(df.columns) - set(RESULT_DTYPES)
    if extra:
        raise ValueError(f"result frame has unexpected columns: {sorted(extra)}")
    df = df[list(RESULT_DTYPES)]
    for column, dtype in RESULT_DTYPES.items():
        df[column] = df[column].astype(dtype)
    return df


def empty_results() -> pd.DataFrame:
    """An empty frame with the correct schema, for tests and for degenerate runs."""
    return pd.DataFrame({c: pd.Series(dtype=d) for c, d in RESULT_DTYPES.items()})
