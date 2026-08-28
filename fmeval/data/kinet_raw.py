"""Reader for raw kinet solver output.

Layout is a flat HDF5 file (no groups) of ``(N_sim, C, T, X, Y)`` float64 datasets, chunked
one frame per chunk. Root attributes are JSON strings. Verified against
``D2Q9_shape-256-256_T-10000_H-dc804f.h5`` (167 GiB) and its 1.7 GB T=101 sibling.

Three quirks of this format, each handled below:

* ``temperature`` is stored ``(1, 1, T, 1, 1)`` -- spatially degenerate and constant at
  1/3. It is a solver parameter, not a field, and is excluded.
* ``pressure`` is bitwise ``density * float64(1/3)`` (isothermal D2Q9, ``c_s^2 = 1/3``);
  it differs from ``density / 3`` only by the last ulp, since multiply and divide round
  differently. Verified across t = 1, 5000, 10000. Carrying both doubles the I/O for no
  information and injects a guaranteed rho=1.0 pair into the cross-metric correlation
  matrix used for pruning, so it is excluded unless asked for.
* ``stability_scale`` and ``stabilized_time_scale`` are all-NaN at t=0, and
  ``time_scale[0]`` is NaN. Start at t=1. Never use ``time_scale`` as a clock -- it is a
  solver stability quantity, roughly constant at 0.5; use the ``time`` dataset.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from . import remote as _remote
from ._timeaxis import TimeAxisMode, read_time_axis
from .base import FIELDS, GridSpec, NanPolicy, Trajectory, register_reader
from .locate import is_url

#: Canonical name -> dataset name in the file.
FIELD_MAP: dict[str, str] = {
    "density": "density",
    "velocity": "velocity",
    "vorticity": "vorticity",
    "pressure": "pressure",
    "distribution": "F",
}

#: Stored but excluded: spatially degenerate, a parameter rather than a field.
DEGENERATE: frozenset[str] = frozenset({"temperature"})

#: Stored but reconstructible from a primitive to within an ulp; excluded by default.
REDUNDANT: frozenset[str] = frozenset({"pressure"})


def _frames_from_discretization(disc: dict) -> int | None:
    """Frame count implied by the root ``discretization`` attribute, or None if absent.

    ``temporal.grid`` counts solver **steps**. Frame 0 is the initial condition, so a file
    holds one more *frame* than it has steps. Measured on
    ``D2Q9_shape-256-256_T-10000_H-dc804f.h5``: ``temporal.grid`` is 10000 while
    ``time.shape`` is ``(10001,)``.

    This is a cross-check rather than the source of the count. ``time.shape[0]`` is the
    length of the very axis being described, so it cannot be off by one, and reading a
    shape is free. Note also that ``temporal.length`` is 10000.0 in *lattice-step* units
    while the physical timestep is 2.2552744890219753e-4, so the attribute cannot supply
    the clock either -- only the number of entries on it.
    """
    temporal = disc.get("temporal") if isinstance(disc, dict) else None
    if not isinstance(temporal, dict) or "grid" not in temporal:
        return None
    return int(temporal["grid"]) + 1


@register_reader("kinet_raw")
class KinetRawTrajectory(Trajectory):
    """One rollout from a flat kinet HDF5 file."""

    def __init__(
        self,
        path: str | Path,
        *,
        chunk_cache_mb: int = 32,
        nan_policy: NanPolicy = "error",
        include_redundant: bool = False,
        periodic: Sequence[bool] | None = None,
        sim_index: int = 0,
        time_axis: TimeAxisMode = "auto",
    ) -> None:
        """Open a kinet raw HDF5 file, locally or over HTTP.

        Args:
            path: Path to the ``.h5`` file, or an ``https://`` URL of the published copy.
            chunk_cache_mb: h5py chunk cache. The default h5py cache is 1 MB, which is
                smaller than one velocity chunk (exactly 1 MB at 256^2), so raising it is
                a free win.
            nan_policy: ``"error"``, ``"warn"`` or ``"ignore"`` for non-finite values.
            include_redundant: Expose ``pressure`` even though it is ``density * c_s^2``.
            periodic: Per-axis periodicity. Raw kinet files do not record it, so it comes
                from the dataset config; defaults to fully periodic, which is correct for
                the doubly-periodic case family.
            sim_index: Index along the leading simulation axis.
            time_axis: How to read the clock. See ``fmeval.data._timeaxis``; the default
                only changes behaviour for a remote file whose clock is chunked per frame.
        """
        self.source = str(path)
        self.is_remote = is_url(path)
        self.location_source = "url" if self.is_remote else "local"
        self.nan_policy = nan_policy
        self._include_redundant = include_redundant
        self._sim = sim_index
        self._remote: _remote.HTTPRangeFile | None = None
        if self.is_remote:
            # `path` stays None: `Path(url)` collapses the `//` and its `.exists()` is a
            # lie that would be believed by the first caller to check it.
            self.path = None
            self._file, self._remote = _remote.open_h5(
                self.source, chunk_cache_mb=chunk_cache_mb
            )
        else:
            self.path = Path(path)
            self._file = h5py.File(
                self.path, "r", rdcc_nbytes=chunk_cache_mb * 2**20, rdcc_nslots=10007
            )

        disc = json.loads(self._file.attrs["discretization"])
        shape = tuple(int(n) for n in disc["spatial"]["grid"])
        length = tuple(float(v) for v in disc["spatial"]["length"])
        spacing = tuple(l / n for l, n in zip(length, shape))
        n_spatial = len(shape)
        periodic_t = (
            tuple(bool(p) for p in periodic) if periodic is not None
            else (True,) * n_spatial
        )
        self._grid = GridSpec(
            shape=shape,
            spacing=spacing,
            periodic=periodic_t,
            dims=("x", "y", "z")[:n_spatial],
            origin=(0.0,) * n_spatial,
        )
        self._times = read_time_axis(
            self._file["time"], remote=self.is_remote, mode=time_axis
        )
        n_frames = len(self._times)
        declared = _frames_from_discretization(disc)
        if declared is not None and declared != n_frames:
            raise ValueError(
                f"{self.source}: the `time` dataset has {n_frames} entries but "
                f"discretization.temporal.grid implies {declared}. A wrong frame count "
                "silently corrupts every dataset.time selection downstream."
            )

        available = []
        for canonical, dataset in FIELD_MAP.items():
            if canonical in DEGENERATE:
                continue
            if canonical in REDUNDANT and not include_redundant:
                continue
            if dataset not in self._file:
                continue
            ds = self._file[dataset]
            if ds.ndim != n_spatial + 3:  # (N, C, T, *spatial)
                continue
            if ds.shape[1] != FIELDS[canonical].n_channels(n_spatial):
                continue
            if ds.shape[2] != n_frames:
                raise ValueError(
                    f"{self.source}: {dataset} has {ds.shape[2]} frames but the `time` "
                    f"dataset has {n_frames}."
                )
            available.append(canonical)
        self._fields = tuple(available)

    # --- Trajectory ---------------------------------------------------------------

    @property
    def fields(self) -> tuple[str, ...]:
        return self._fields

    @property
    def times(self) -> np.ndarray:
        return self._times

    @property
    def grid(self) -> GridSpec:
        return self._grid

    @property
    def meta(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        for key, value in self._file.attrs.items():
            if isinstance(value, (bytes, str)):
                text = value.decode() if isinstance(value, bytes) else value
                try:
                    attrs[key] = json.loads(text)
                except (ValueError, TypeError):
                    attrs[key] = text
            elif isinstance(value, np.generic):
                attrs[key] = value.item()
            else:
                attrs[key] = value
        meta: dict[str, Any] = {
            "path": self.source,
            "format": "kinet_raw",
            "n_frames": len(self._times),
            "fields": list(self._fields),
            "source": self.location_source,
            "source_attrs": attrs,
        }
        if self._remote is not None:
            meta["remote"] = self._remote.provenance()
        return meta

    def read_frame(self, t: int, fields: Sequence[str]) -> dict[str, np.ndarray]:
        """Read one frame.

        ``ds[sim, :, t]`` returns ``(C, *spatial)`` directly for every channel count, so
        there is no squeeze, reshape or scalar special case. The time position is always a
        plain int -- never a slice. See the module docstring in ``base.py``.
        """
        out: dict[str, np.ndarray] = {}
        for name in fields:
            ds = self._file[FIELD_MAP[name]]
            out[name] = np.asarray(ds[self._sim, :, t], dtype=np.float64)
        return out

    def close(self) -> None:
        if getattr(self, "_file", None) is not None:
            self._file.close()
            self._file = None  # type: ignore[assignment]
        if getattr(self, "_remote", None) is not None:
            self._remote.close()
            self._remote = None
