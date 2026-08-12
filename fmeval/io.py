"""Run folders: creation, provenance, and reloading.

One folder per metric under test, named ``<metric>_<time>`` where ``<time>`` is
``int(time.time())``. The **same** timestamp is used for every metric in one invocation,
so a multi-metric run produces sibling folders that sort together and are obviously one
experiment.

Everything a folder needs is inside it -- the raw numbers, the resolved config, the
provenance -- so it can be copied to a colleague, attached to an issue, or uploaded to
Overleaf and still regenerate its own report. The rule is that no number appears in the
report without a machine-readable source in the same folder.

CSV rather than Parquet: ``pyarrow`` is not installed and this is a shared environment not
worth fighting. Large frames are gzipped, which pandas handles from the extension alone.
"""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import subprocess
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

#: Gzip the tidy frame above this many rows.
GZIP_ROWS = 500_000


@dataclass(frozen=True)
class RunFolder:
    """Layout of one ``results/<name>_<time>/`` directory."""

    root: Path

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def plots(self) -> Path:
        return self.root / "plots"

    @property
    def tables(self) -> Path:
        return self.root / "tables"

    @property
    def sections(self) -> Path:
        return self.root / "sections"

    @property
    def figure_data(self) -> Path:
        return self.data / "figure_data"

    def create(self) -> RunFolder:
        for path in (self.data, self.plots, self.tables, self.sections, self.figure_data):
            path.mkdir(parents=True, exist_ok=True)
        return self


def run_id() -> int:
    """Integer seconds since the epoch, used to stamp every folder of one invocation."""
    return int(time.time())


def make_run_folder(results_root: Path | str, name: str, stamp: int) -> RunFolder:
    """Create ``<results_root>/<name>_<stamp>/`` with its subdirectories."""
    folder = RunFolder(Path(results_root) / f"{name}_{stamp}")
    return folder.create()


# --- writing ------------------------------------------------------------------------


def write_results(folder: RunFolder, df: pd.DataFrame, name: str = "results") -> Path:
    """Write the tidy frame, gzipping when it is large."""
    suffix = ".csv.gz" if len(df) > GZIP_ROWS else ".csv"
    path = folder.data / f"{name}{suffix}"
    df.to_csv(path, index=False)
    return path


def write_table(folder: RunFolder, df: pd.DataFrame, name: str) -> Path:
    """Write one analysis table to ``data/`` as CSV."""
    path = folder.data / f"{name}.csv"
    df.to_csv(path, index=False)
    return path


def write_maps(folder: RunFolder, maps: Mapping[str, np.ndarray]) -> Path | None:
    """Write pointwise metric maps to a compressed npz, or nothing if there are none."""
    if not maps:
        return None
    path = folder.data / "error_maps.npz"
    np.savez_compressed(path, **maps)
    return path


def write_config(folder: RunFolder, resolved: Mapping[str, Any],
                 overrides: list[str] | None = None) -> str:
    """Write the config that produced the numbers, and return its hash.

    ``config.yaml`` is the **fully resolved** tree -- every interpolation expanded and
    every group default materialised -- so it records what actually ran rather than what
    the defaults happened to be that day. ``config_overrides.yaml`` keeps just the
    command-line overrides, which is what you read when diffing two runs.

    Returns:
        Short blake2b hash of the resolved config. Two runs with the same hash used
        identical settings.
    """
    import yaml

    text = yaml.safe_dump(_plain(resolved), sort_keys=True, default_flow_style=False)
    (folder.data / "config.yaml").write_text(text)
    (folder.data / "config_overrides.yaml").write_text(
        yaml.safe_dump(list(overrides or []), default_flow_style=False)
    )
    digest = hashlib.blake2b(text.encode(), digest_size=8).hexdigest()
    (folder.data / "config_hash.txt").write_text(digest + "\n")
    return digest


def copy_documentation(folder: RunFolder) -> Path | None:
    """Copy TEST_DESCRIPTION.md into the run folder.

    A results directory should explain its own numbers after being sent to a colleague or
    uploaded to Overleaf, without needing the repository alongside it.
    """
    import shutil

    source = Path(__file__).resolve().parent.parent / "TEST_DESCRIPTION.md"
    if not source.exists():  # pragma: no cover - present in a checkout
        return None
    target = folder.root / source.name
    shutil.copy(source, target)
    return target


def write_run_meta(folder: RunFolder, **extra: Any) -> Path:
    """Write provenance: git state, environment, package versions, registry snapshot.

    The registry snapshot matters more than it looks: six months from now you need to know
    whether ``nrmse`` meant "normalised by the raw RMS" or "by the fluctuation RMS" when
    that CSV was written.
    """
    meta: dict[str, Any] = {
        "git": _git_state(),
        "host": platform.node(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": _package_versions(),
        "registries": _registry_snapshot(),
        **extra,
    }
    path = folder.data / "run_meta.json"
    path.write_text(json.dumps(meta, indent=2, default=str) + "\n")
    return path


# --- reading ------------------------------------------------------------------------


def read_results(folder: RunFolder | Path, name: str = "results") -> pd.DataFrame:
    """Read a tidy frame back, from either the plain or the gzipped form."""
    data = folder.data if isinstance(folder, RunFolder) else Path(folder) / "data"
    for suffix in (".csv", ".csv.gz"):
        path = data / f"{name}{suffix}"
        if path.exists():
            return pd.read_csv(path)
    raise FileNotFoundError(f"no {name}.csv or {name}.csv.gz in {data}")


def load_runs(pattern: str, root: Path | str = "results") -> pd.DataFrame:
    """Concatenate the results of several run folders, tagged by folder name.

    How a multirun sweep becomes one cross-dataset or cross-metric table.

    Args:
        pattern: Glob relative to ``root``, e.g. ``"mse_*"`` or ``"*_1786224531"``.
        root: Results directory.
    """
    frames = []
    for folder in sorted(Path(root).glob(pattern)):
        if not (folder / "data").is_dir():
            continue
        try:
            df = read_results(folder)
        except FileNotFoundError:
            log.warning("no results in %s; skipping", folder)
            continue
        df["run_dir"] = folder.name
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"no run folders matching {pattern!r} under {root}")
    return pd.concat(frames, ignore_index=True)


# --- provenance helpers ---------------------------------------------------------------


def _plain(obj: Any) -> Any:
    """Convert OmegaConf containers and numpy scalars into plain YAML-safe Python."""
    try:
        from omegaconf import DictConfig, ListConfig, OmegaConf

        if isinstance(obj, (DictConfig, ListConfig)):
            return OmegaConf.to_container(obj, resolve=True)
    except ImportError:  # pragma: no cover - omegaconf is a hard dependency
        pass
    if isinstance(obj, Mapping):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def _git_state() -> dict[str, Any]:
    def _run(*args: str) -> str | None:
        try:
            out = subprocess.run(
                ["git", *args], capture_output=True, text=True, timeout=10,
                cwd=Path(__file__).resolve().parent.parent,
            )
            return out.stdout.strip() if out.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            return None

    status = _run("status", "--porcelain")
    return {
        "sha": _run("rev-parse", "HEAD"),
        "branch": _run("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(status) if status is not None else None,
    }


def _package_versions() -> dict[str, str]:
    from importlib.metadata import PackageNotFoundError, version

    out = {}
    for name in ("numpy", "scipy", "h5py", "pandas", "matplotlib", "hydra-core",
                 "omegaconf"):
        try:
            out[name] = version(name)
        except PackageNotFoundError:  # pragma: no cover
            pass
    return out


def _registry_snapshot() -> dict[str, Any]:
    """What each registered metric and degradation meant at the time of the run."""
    from degradations import registry as deg
    from metrics import registry as met

    met.discover()
    deg.discover()
    return {
        "metrics": {
            s.name: {
                "tracker_id": s.tracker_id,
                "arity": s.arity,
                "units": s.units,
                "reduction": s.reduction,
                "has_pointwise": s.has_pointwise,
                "differentiable": s.differentiable,
                "module": s.module,
                "doc": s.doc.splitlines()[0] if s.doc else "",
            }
            for s in met.REGISTRY.values()
        },
        "degradations": {
            s.name: {
                "family": s.family,
                "severity_name": s.severity_name,
                "severity_units": s.severity_units,
                "severity_direction": s.severity_direction,
                "ordinal": s.ordinal,
                "stochastic": s.stochastic,
                "module": s.module,
                "doc": s.doc.splitlines()[0] if s.doc else "",
            }
            for s in deg.REGISTRY.values()
        },
    }
