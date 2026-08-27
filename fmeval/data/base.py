"""The format-independent data contract.

Three rules, and everything else follows.

**1. Canonical array layout is channel-first with spatial axes trailing in ``(x, y, z)``
order.** kinet stores ``(C, X, Y, Z)`` in 3D and drops dimensions right to left, so 2D is
``(C, X, Y)`` and 1D is ``(C, X)``. We adopt that verbatim rather than converting to the
numpy image convention: converting would mean a transpose on every read and a permanent
mismatch with the solver's own output. Everything downstream is written against "the
trailing ``n_spatial`` axes, in order x, y, z", which is what makes 3D a non-event.

**2. Readers translate into a fixed field vocabulary** (:data:`FIELDS`), tagged primitive
or derived. The remap in :mod:`fmeval.remap` dispatches on that tag: primitives are
block-averaged, derived fields are recomputed from remapped primitives.

**3. The time axis is never sliced.** Readers index one frame at a time with an ``int``.
The kinet HDF5 files are chunked one frame per chunk, so ``density[0, 0, :, i, j]`` would
touch all 10001 chunks -- 5 GB of I/O for 80 KB of data. :meth:`Trajectory.read_frame`
asserts the index is an integer, and a test monkeypatches ``h5py`` to prove no reader
violates it.
"""

from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field as dc_field
from typing import Any, Literal

import numpy as np

FieldKind = Literal["primitive", "derived"]
NanPolicy = Literal["error", "warn", "ignore"]


@dataclass(frozen=True)
class FieldSpec:
    """One entry of the canonical field vocabulary."""

    name: str
    kind: FieldKind
    #: How many channels this field has on an ``n_spatial``-dimensional grid.
    channels: str  # "1" | "n_spatial" | "vorticity" | "9"
    description: str

    def n_channels(self, n_spatial: int) -> int:
        if self.channels == "1":
            return 1
        if self.channels == "n_spatial":
            return n_spatial
        if self.channels == "vorticity":
            # Vorticity is a pseudo-scalar in 2D and a vector in 3D.
            return 1 if n_spatial == 2 else 3
        return int(self.channels)


#: The canonical vocabulary. Readers map their own names onto these.
FIELDS: dict[str, FieldSpec] = {
    "density": FieldSpec("density", "primitive", "1", "Mass density."),
    "velocity": FieldSpec(
        "velocity", "primitive", "n_spatial",
        "Velocity; channel i is the component along dims[i]."
    ),
    "distribution": FieldSpec(
        "distribution", "primitive", "9", "Lattice-Boltzmann distribution (D2Q9)."
    ),
    "vorticity": FieldSpec(
        "vorticity", "derived", "vorticity",
        "Curl of the velocity. Recomputed from velocity on the analysis grid, never "
        "block-averaged -- see fmeval.derived."
    ),
    "pressure": FieldSpec(
        "pressure", "derived", "1",
        "Pressure. For the isothermal D2Q9 solver this is density * c_s^2 with "
        "c_s^2 = 1/3, i.e. density/3 to within one ulp."
    ),
    "temperature": FieldSpec(
        "temperature", "primitive", "1", "Temperature (degenerate for isothermal runs)."
    ),
}

CANONICAL_FIELDS: frozenset[str] = frozenset(FIELDS)
PRIMITIVE_FIELDS: frozenset[str] = frozenset(
    n for n, s in FIELDS.items() if s.kind == "primitive"
)
DERIVED_FIELDS: frozenset[str] = frozenset(
    n for n, s in FIELDS.items() if s.kind == "derived"
)


@dataclass(frozen=True)
class GridSpec:
    """Geometry of one analysis grid.

    Attributes:
        shape: Spatial extents in ``dims`` order, e.g. ``(256, 256)`` for ``("x", "y")``.
        spacing: Cell size along each axis, same order.
        periodic: Whether each axis wraps.
        dims: Axis names, always a prefix of ``("x", "y", "z")``.
        origin: Coordinate of the first cell along each axis.
    """

    shape: tuple[int, ...]
    spacing: tuple[float, ...]
    periodic: tuple[bool, ...]
    dims: tuple[str, ...] = ("x", "y")
    origin: tuple[float, ...] = (0.0, 0.0)

    def __post_init__(self) -> None:
        n = len(self.shape)
        for name, val in (
            ("spacing", self.spacing),
            ("periodic", self.periodic),
            ("dims", self.dims),
        ):
            if len(val) != n:
                raise ValueError(
                    f"GridSpec.{name} has length {len(val)}, expected {n} to match shape"
                )
        if self.dims != ("x", "y", "z")[:n]:
            raise ValueError(
                f"GridSpec.dims must be a prefix of ('x','y','z'); got {self.dims}"
            )

    @property
    def n_spatial(self) -> int:
        return len(self.shape)

    @property
    def length(self) -> tuple[float, ...]:
        """Physical domain extent along each axis."""
        return tuple(n * dx for n, dx in zip(self.shape, self.spacing))

    def axis(self, dim: str) -> int:
        """Negative array axis index for a named dimension.

        Operators must resolve "the x axis" through this rather than hardcoding ``-2``,
        because the answer depends on ``n_spatial``.
        """
        if dim not in self.dims:
            raise ValueError(f"unknown dim {dim!r}; grid has {self.dims}")
        return -self.n_spatial + self.dims.index(dim)

    def coarsened(self, factor: int) -> GridSpec:
        """The grid this one becomes after block-averaging by ``factor``.

        Spacing grows by exactly ``factor`` -- the detail that, if forgotten, inflates
        every spectral derivative by that same factor.
        """
        if any(n % factor for n in self.shape):
            raise ValueError(
                f"factor {factor} does not divide grid {self.shape}"
            )
        return GridSpec(
            shape=tuple(n // factor for n in self.shape),
            spacing=tuple(dx * factor for dx in self.spacing),
            periodic=self.periodic,
            dims=self.dims,
            origin=self.origin,
        )


@dataclass(frozen=True)
class Frame:
    """One time slice of a trajectory, on one grid."""

    index: int
    """Index into the *source* time axis, not into the selection."""
    time: float
    fields: dict[str, np.ndarray]
    """Canonical name -> ``(C, *spatial)`` float64."""
    grid: GridSpec
    members: dict[str, np.ndarray] | None = None
    """Canonical name -> ``(N, C, *spatial)`` float64, or None on a deterministic frame.

    ``fields[name]`` is the reference realization -- the truth a metric is scored
    against -- and ``members[name]`` is the predictive ensemble standing in for a
    distribution over it. The two are deliberately *not* required to agree in any way:
    the reference is not the member mean, and for an exchangeable ensemble it is simply
    one more draw from the same process. A probabilistic metric consumes both.
    """

    @property
    def has_members(self) -> bool:
        return self.members is not None

    def __getitem__(self, name: str) -> np.ndarray:
        return self.fields[name]

    def with_fields(
        self,
        fields: dict[str, np.ndarray],
        grid: GridSpec,
        members: dict[str, np.ndarray] | None = None,
    ) -> Frame:
        """A copy carrying different field arrays, e.g. after a remap or a degradation.

        Members are dropped unless passed explicitly. Silently carrying them would
        outlive the operation that invalidated them: after a remap the stored stack is
        still on the old grid, and after a degradation it no longer matches the field
        beside it. Every caller that means to keep members says so.
        """
        return Frame(
            index=self.index, time=self.time, fields=fields, grid=grid, members=members
        )


@dataclass(frozen=True)
class TimeSelection:
    """Which frames of a trajectory to evaluate.

    Attributes:
        start: First source index. Defaults to 1 for kinet data, where several fields are
            all-NaN at t=0.
        stop: Exclusive upper bound, or None for the end.
        reduction: Evaluate every Nth frame. This is the temporal size knob: a 10001-frame
            trajectory at ``reduction=50`` is 201 frames.
        max_frames: Hard cap, applied *after* reduction.
    """

    start: int = 0
    stop: int | None = None
    reduction: int = 1
    max_frames: int | None = None

    def __post_init__(self) -> None:
        if self.reduction < 1:
            raise ValueError(f"reduction must be >= 1, got {self.reduction}")
        if self.start < 0:
            raise ValueError(f"start must be >= 0, got {self.start}")

    def resolve(self, n_frames: int) -> np.ndarray:
        """The source indices this selection picks out of ``n_frames``."""
        stop = n_frames if self.stop is None else min(self.stop, n_frames)
        idx = np.arange(self.start, stop, self.reduction, dtype=int)
        if self.max_frames is not None:
            idx = idx[: self.max_frames]
        return idx


class Trajectory(ABC):
    """One simulation rollout, read lazily one frame at a time.

    Subclasses implement :meth:`read_frame` plus the four properties. Validation lives in
    the concrete :meth:`frame`, so every future reader inherits it for free.
    """

    nan_policy: NanPolicy = "error"

    is_ensemble: bool = False
    """Whether :meth:`read_frame` also returns ``f"{name}__members"`` member stacks.

    Defaults False, so every reader that predates ensembles takes exactly the code path
    it took before: the validation below is skipped entirely and the frame it yields
    carries ``members=None``.
    """

    # --- to implement -------------------------------------------------------------

    @property
    @abstractmethod
    def fields(self) -> tuple[str, ...]:
        """Canonical field names actually available from this source."""

    @property
    @abstractmethod
    def times(self) -> np.ndarray:
        """Physical time of every frame on the source axis, shape ``(T,)``."""

    @property
    @abstractmethod
    def grid(self) -> GridSpec:
        """Native grid of the stored data."""

    @property
    @abstractmethod
    def meta(self) -> dict[str, Any]:
        """Provenance: path, format, source attributes, notes."""

    @abstractmethod
    def read_frame(self, t: int, fields: Sequence[str]) -> dict[str, np.ndarray]:
        """Read one frame. ``t`` is an int index into the source time axis."""

    # --- provided -----------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.times)

    def frame(self, t: int, fields: Sequence[str]) -> Frame:
        """Read and validate one frame.

        Raises:
            TypeError: If ``t`` is not an integer -- the guard against slicing the time
                axis, which would be catastrophically slow on chunked HDF5.
            ValueError: On a shape, channel-count or finiteness violation.
        """
        if not isinstance(t, (int, np.integer)) or isinstance(t, bool):
            raise TypeError(
                f"frame index must be an int, got {type(t).__name__}. Slicing the time "
                "axis reads every chunk in the file; iterate frame by frame instead."
            )
        requested = tuple(fields)
        unknown = set(requested) - CANONICAL_FIELDS
        if unknown:
            raise ValueError(f"unknown canonical field(s): {sorted(unknown)}")
        missing = set(requested) - set(self.fields)
        if missing:
            raise ValueError(
                f"{sorted(missing)} not available from this source; has {list(self.fields)}"
            )

        raw = self.read_frame(int(t), requested)
        grid = self.grid
        out: dict[str, np.ndarray] = {}
        for name in requested:
            arr = np.ascontiguousarray(raw[name], dtype=np.float64)
            want_c = FIELDS[name].n_channels(grid.n_spatial)
            want = (want_c, *grid.shape)
            if arr.shape != want:
                raise ValueError(
                    f"{name} at t={t}: reader returned {arr.shape}, expected {want} "
                    f"(C, *spatial) with spatial in {grid.dims} order"
                )
            self._check_finite(name, arr, t)
            out[name] = arr

        members = self._read_members(raw, requested, grid, t) if self.is_ensemble else None
        return Frame(
            index=int(t), time=float(self.times[t]), fields=out, grid=grid, members=members
        )

    def _read_members(
        self,
        raw: dict[str, np.ndarray],
        requested: Sequence[str],
        grid: GridSpec,
        t: int,
    ) -> dict[str, np.ndarray]:
        """Validate and collect the ``(N, C, *spatial)`` member stacks of one frame.

        The member axis leads. Checking it explicitly matters more than the usual shape
        guard: a stack handed over as ``(C, N, *spatial)`` has the right size and the
        right dtype, so every probabilistic metric would happily reduce over the channel
        axis instead of the ensemble and return a plausible wrong number.
        """
        members: dict[str, np.ndarray] = {}
        for name in requested:
            key = f"{name}__members"
            if key not in raw:
                raise ValueError(
                    f"{name} members at t={t}: reader declares is_ensemble but returned "
                    f"no {key!r} key"
                )
            arr = np.ascontiguousarray(raw[key], dtype=np.float64)
            want_c = FIELDS[name].n_channels(grid.n_spatial)
            if arr.ndim != 2 + grid.n_spatial or arr.shape[1:] != (want_c, *grid.shape):
                raise ValueError(
                    f"{name} members at t={t}: reader returned {arr.shape}, expected "
                    f"(N, {want_c}, *{grid.shape}) with the member axis leading"
                )
            if arr.shape[0] < 1:
                raise ValueError(
                    f"{name} members at t={t}: empty ensemble, expected at least one member"
                )
            self._check_finite(f"{name} members", arr, t)
            members[name] = arr
        return members

    def _check_finite(self, name: str, arr: np.ndarray, t: int) -> None:
        if self.nan_policy == "ignore" or np.isfinite(arr).all():
            return
        n_bad = int((~np.isfinite(arr)).sum())
        msg = f"{name} at t={t} has {n_bad} non-finite value(s) of {arr.size}"
        if self.nan_policy == "error":
            raise ValueError(
                msg + ". Several kinet fields are all-NaN at t=0; set dataset.time.start=1"
            )
        warnings.warn(msg, RuntimeWarning, stacklevel=3)

    def iter_frames(
        self, fields: Sequence[str], selection: TimeSelection | None = None
    ) -> Iterator[Frame]:
        """Yield selected frames in ascending index order, for sequential I/O."""
        selection = selection or TimeSelection()
        for t in selection.resolve(len(self)):
            yield self.frame(int(t), fields)

    def close(self) -> None:
        """Release any file handles. Idempotent."""

    def __enter__(self) -> Trajectory:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


READERS: dict[str, type[Trajectory]] = {}


def register_reader(name: str):
    """Register a Trajectory subclass under a format name used in dataset configs."""

    def _decorate(cls: type[Trajectory]) -> type[Trajectory]:
        if name in READERS:
            raise ValueError(f"duplicate reader format {name!r}")
        READERS[name] = cls
        return cls

    return _decorate
