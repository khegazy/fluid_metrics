"""Reader for the PolymathicAI *Well* layout.

The second format, and therefore the test of whether the data contract actually holds. The
whole reader is one method plus four properties; the evaluator, the pipeline, the
degradations and every metric are untouched by its existence.

Three differences from the raw kinet layout have to be absorbed here and nowhere else:

* **float32 rather than float64.** Cast on read; the canonical contract is float64.
* **No channel axis on scalars.** ``t0_fields/density`` is ``(sim, T, X, Y)``, so a channel
  axis of length one is inserted.
* **Velocity is channel-LAST**, ``t1_fields/velocity`` is ``(sim, T, X, Y, D)``. A
  ``moveaxis`` fixes it. This is the one line where a mistake would be invisible on square
  data, which is why the fixtures write u = 1 and v = 2 and the grids are non-square.

The spatial axis order is the same as kinet's: the file declares
``dimensions.attrs["spatial_dims"] = ["x", "y"]`` and stores them in that order, so no
transpose is needed -- only the channel move.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from .base import FIELDS, GridSpec, NanPolicy, Trajectory, register_reader

#: Canonical name -> (group, dataset). Velocity lives in the rank-1 group.
FIELD_MAP: dict[str, tuple[str, str]] = {
    "density": ("t0_fields", "density"),
    "pressure": ("t0_fields", "pressure"),
    "temperature": ("t0_fields", "temperature"),
    "vorticity": ("t0_fields", "vorticity"),
    "velocity": ("t1_fields", "velocity"),
}

#: Reconstructible from a primitive; excluded unless asked for, as in the raw reader.
REDUNDANT: frozenset[str] = frozenset({"pressure"})

#: Constant for an isothermal run, so it carries no information as a field. Unlike the raw
#: format the Well writer broadcasts it to the full grid, so it cannot be detected by shape.
DEGENERATE: frozenset[str] = frozenset({"temperature"})


@register_reader("well")
class WellTrajectory(Trajectory):
    """One rollout from a Well-format HDF5 file."""

    def __init__(
        self,
        path: str | Path,
        *,
        chunk_cache_mb: int = 32,
        nan_policy: NanPolicy = "error",
        include_redundant: bool = False,
        include_degenerate: bool = False,
        sim_index: int = 0,
    ) -> None:
        """Open a Well-format file.

        Args:
            path: Path to the ``.h5`` file.
            chunk_cache_mb: h5py chunk cache size.
            nan_policy: ``"error"``, ``"warn"`` or ``"ignore"`` for non-finite values.
            include_redundant: Expose ``pressure``.
            include_degenerate: Expose ``temperature``, which is constant for an
                isothermal run and therefore not a field in any useful sense.
            sim_index: Index along the leading trajectory axis.
        """
        self.path = Path(path)
        self.nan_policy = nan_policy
        self._sim = sim_index
        self._file = h5py.File(
            self.path, "r", rdcc_nbytes=chunk_cache_mb * 2**20, rdcc_nslots=10007
        )

        dims = self._file["dimensions"]
        names = [_text(n) for n in dims.attrs.get("spatial_dims", ["x", "y"])]
        expected = ("x", "y", "z")[: len(names)]
        if tuple(names) != expected:
            raise ValueError(
                f"{self.path.name}: spatial_dims is {names}, expected {list(expected)}. "
                "A different order would need a transpose, which this reader does not do."
            )
        coords = [np.asarray(dims[name][:], dtype=np.float64) for name in names]
        shape = tuple(len(c) for c in coords)
        spacing = tuple(
            float(c[1] - c[0]) if len(c) > 1 else 1.0 for c in coords
        )
        periodic = tuple(
            f"{name}_periodic" in self._file.get("boundary_conditions", {})
            for name in names
        )
        self._grid = GridSpec(
            shape=shape,
            spacing=spacing,
            periodic=periodic,
            dims=tuple(names),
            origin=tuple(float(c[0]) for c in coords),
        )
        self._times = np.asarray(dims["time"][:], dtype=np.float64)

        available = []
        for canonical, (group, dataset) in FIELD_MAP.items():
            if canonical in DEGENERATE and not include_degenerate:
                continue
            if canonical in REDUNDANT and not include_redundant:
                continue
            if group not in self._file or dataset not in self._file[group]:
                continue
            ds = self._file[group][dataset]
            n_channels = FIELDS[canonical].n_channels(len(shape))
            # Rank-0 fields: (sim, T, *spatial). Rank-1: (sim, T, *spatial, D).
            wanted = 2 + len(shape) + (1 if n_channels > 1 else 0)
            if ds.ndim != wanted:
                continue
            if n_channels > 1 and ds.shape[-1] != n_channels:
                continue
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
        attrs = {
            key: _text(value) if isinstance(value, (bytes, str))
            else value.item() if isinstance(value, np.generic) else value
            for key, value in self._file.attrs.items()
        }
        return {
            "path": str(self.path),
            "format": "well",
            "n_frames": len(self._times),
            "fields": list(self._fields),
            "source_attrs": attrs,
        }

    def read_frame(self, t: int, fields: Sequence[str]) -> dict[str, np.ndarray]:
        """Read one frame, normalising channel placement and dtype.

        The time position is always a plain int, never a slice -- the same invariant the raw
        reader observes, for the same reason.
        """
        out: dict[str, np.ndarray] = {}
        for name in fields:
            group, dataset = FIELD_MAP[name]
            ds = self._file[group][dataset]
            if FIELDS[name].n_channels(self._grid.n_spatial) > 1:
                # (X, Y, D) -> (D, X, Y). The one line where an error would be invisible
                # on a square grid.
                out[name] = np.moveaxis(
                    np.asarray(ds[self._sim, t], dtype=np.float64), -1, 0
                )
            else:
                out[name] = np.asarray(ds[self._sim, t], dtype=np.float64)[np.newaxis]
        return out

    def close(self) -> None:
        if getattr(self, "_file", None) is not None:
            self._file.close()
            self._file = None  # type: ignore[assignment]


def _text(value: object) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)
