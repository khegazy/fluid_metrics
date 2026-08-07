"""Evaluate metrics against a degradation ladder and write a run folder per metric.

    uv run python evaluate.py metrics=[mse] dataset=kinet_re5e4_dev
    uv run python evaluate.py 'metrics=[mae,mse,nrmse]' dataset=kinet_re5e4 \\
        dataset.time.reduction=100
    uv run python evaluate.py metrics=[mse] degradation=quick
    uv run python evaluate.py metrics=[mse] analysis_grid.resolution=128

Each metric gets its own ``results/<metric>_<time>/`` folder, all sharing one timestamp so
a multi-metric run is obviously one experiment. The folders carry the raw numbers, the
resolved config and full provenance, so they regenerate their own report without the repo.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig, OmegaConf

from degradations import registry as deg_registry
from fmeval import io as fio
from fmeval.data.base import READERS, TimeSelection, Trajectory
from fmeval.derived import recompute_frame
from fmeval.ladder import build_ladder
from fmeval.pipeline import DatasetInfo, MapRequest, run
from metrics import registry as metric_registry

log = logging.getLogger(__name__)


def open_trajectory(cfg: DictConfig) -> Trajectory:
    """Construct the reader named by ``dataset.format``.

    Explicit imports rather than a package walk: readers are a small closed set maintained
    with the harness, unlike metrics and degradations which are open contributor sets.
    """
    from fmeval.data import kinet_raw  # noqa: F401  (registers "kinet_raw")

    fmt = cfg.dataset.format
    if fmt not in READERS:
        raise KeyError(f"unknown dataset format {fmt!r}; available: {sorted(READERS)}")
    reader_kwargs = OmegaConf.to_container(cfg.dataset.get("reader", {}), resolve=True)
    return READERS[fmt](cfg.dataset.path, **reader_kwargs)


def select_fields(cfg: DictConfig, trajectory: Trajectory,
                  specs: list[metric_registry.MetricSpec]) -> list[str]:
    """Fields to read: the config list if given, else what the metrics actually accept."""
    requested = cfg.get("fields") or cfg.dataset.get("fields")
    available = list(trajectory.fields)
    if requested:
        missing = [f for f in requested if f not in available]
        if missing:
            raise ValueError(
                f"dataset {cfg.dataset.name!r} does not provide {missing}; "
                f"it has {available}"
            )
        candidates = list(requested)
    else:
        candidates = available

    wanted: list[str] = []
    for field in candidates:
        if any(s.fields == ("*",) or field in s.fields for s in specs):
            wanted.append(field)
    if not wanted:
        raise ValueError(
            f"no field in {candidates} is accepted by any of "
            f"{[s.name for s in specs]}"
        )
    return wanted


def dataset_info(cfg: DictConfig) -> DatasetInfo:
    complexity = cfg.dataset.get("complexity") or {}
    return DatasetInfo(
        name=cfg.dataset.name,
        trajectory=cfg.dataset.get("trajectory", ""),
        family=complexity.get("family", ""),
        rank=complexity.get("rank"),
        params=OmegaConf.to_container(complexity.get("params", {}), resolve=True) or {},
    )


@hydra.main(version_base=None, config_path="configs", config_name="config")
def main(cfg: DictConfig) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout, force=True,
    )
    started = time.perf_counter()
    stamp = fio.run_id()

    specs = [metric_registry.get(name) for name in cfg.metrics]
    deg_registry.discover()
    rungs = build_ladder(
        OmegaConf.to_container(cfg.degradation.ladder, resolve=True),
        include_reference=cfg.degradation.get("include_reference", True),
        only=list(cfg.degradation.get("only") or []),
        skip=list(cfg.degradation.get("skip") or []),
    )
    n_axes = len({r.label for r in rungs if not r.is_reference})
    log.info("ladder: %d rungs over %d axes", len(rungs), n_axes)

    trajectory = open_trajectory(cfg)
    try:
        fields = select_fields(cfg, trajectory, specs)
        selection = TimeSelection(**OmegaConf.to_container(cfg.dataset.time, resolve=True))
        n_frames = len(selection.resolve(len(trajectory)))
        resolution = cfg.analysis_grid.get("resolution")
        log.info(
            "dataset %s: %d of %d frames (reduction %d), fields %s, analysis grid %s",
            cfg.dataset.name, n_frames, len(trajectory), selection.reduction, fields,
            resolution or trajectory.grid.shape[0],
        )

        if cfg.dataset.get("recompute_derived", True):
            trajectory = _RecomputingTrajectory(trajectory)

        report_cfg = cfg.get("report", {})
        map_cfg = report_cfg.get("error_map", {}) if report_cfg else {}
        maps = MapRequest(
            enabled=bool(map_cfg.get("enabled", False)),
            frames=list(map_cfg.get("frames") or []),
            axes=list(map_cfg.get("axes") or []),
            fields=list(map_cfg.get("fields") or []),
        )

        result = run(
            trajectory,
            specs,
            rungs,
            fields=fields,
            selection=selection,
            dataset=dataset_info(cfg),
            seed=int(cfg.seed),
            analysis_resolution=resolution,
            remap_method=cfg.analysis_grid.get("method", "block_mean"),
            maps=maps,
        )
    finally:
        trajectory.close()

    elapsed = time.perf_counter() - started
    log.info(
        "%d rows in %.1fs (io %.1fs, degrade %.1fs, metrics %.1fs)",
        len(result.rows), elapsed, result.io_seconds, result.degrade_seconds,
        result.metric_seconds,
    )

    overrides = _overrides()
    written = []
    for spec in specs:
        subset = result.rows[result.rows["metric"] == spec.name]
        folder = fio.make_run_folder(cfg.paths.results, spec.name, stamp)
        fio.write_results(folder, subset)
        digest = fio.write_config(folder, cfg, overrides)
        prefix = f"{spec.name}:"
        fio.write_maps(
            folder,
            {k: v for k, v in result.maps.items() if k.startswith(prefix)},
        )
        fio.write_run_meta(
            folder,
            run_id=stamp,
            config_hash=digest,
            metric=spec.name,
            dataset=cfg.dataset.name,
            n_frames=result.n_frames,
            n_rows=int(len(subset)),
            fields=fields,
            analysis_grid=resolution or trajectory.grid.shape[0],
            ladder_axes=sorted({r.label for r in rungs if not r.is_reference}),
            n_rungs=len(rungs),
            seed=int(cfg.seed),
            timings={
                "total_s": elapsed,
                "io_s": result.io_seconds,
                "degrade_s": result.degrade_seconds,
                "metric_s": result.metric_seconds,
            },
            command=" ".join(sys.argv),
        )
        written.append(folder.root)

    for path in written:
        log.info("wrote %s", path)


class _RecomputingTrajectory:
    """Wrapper that replaces stored derived fields with our own operator.

    Without this the native grid would carry the solver's lattice-stencil vorticity while
    every coarse grid carries a spectral one, and a grid-independence comparison would be
    measuring the difference between two discretisations rather than between two grids.
    """

    def __init__(self, inner: Trajectory) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def __len__(self) -> int:
        return len(self._inner)

    def frame(self, t: int, fields):
        return recompute_frame(self._inner.frame(t, fields))

    def iter_frames(self, fields, selection=None):
        for frame in self._inner.iter_frames(fields, selection):
            yield recompute_frame(frame)

    def close(self) -> None:
        self._inner.close()


def _overrides() -> list[str]:
    try:
        from hydra.core.hydra_config import HydraConfig

        return list(HydraConfig.get().overrides.task)
    except Exception:  # pragma: no cover - outside a Hydra run
        return []


if __name__ == "__main__":
    main()
