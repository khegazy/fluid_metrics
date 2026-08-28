"""Builders for tiny synthetic HDF5 files mirroring the real on-disk schemas.

These are deliberately faithful to the *quirks*, not just the shapes: JSON-string root
attributes, all-NaN fields at t=0, the spatially degenerate temperature, and pressure
written as ``density * c_s^2`` rather than ``density / 3`` (they differ in the last ulp).
A fixture that stops reproducing a quirk is itself a signal that the real format has
changed.

Grids are **non-square** (16x8). Every real dataset is square, so a reader that transposes
x and y passes every test on real-shaped data; the fixtures are the only place that bug
can be caught.
"""

from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np

from tests.conftest import synthetic_field

#: Non-square on purpose. See the module docstring.
SHAPE: tuple[int, int] = (16, 8)
N_FRAMES: int = 5


def _time_axis(n: int) -> np.ndarray:
    return np.arange(n, dtype=np.float64) * 0.25


def write_kinet_raw(path: Path, shape: tuple[int, ...] = SHAPE,
                    n_frames: int = N_FRAMES, times: np.ndarray | None = None) -> Path:
    """Write a synthetic file in the raw kinet layout ``(1, C, T, *spatial)``.

    Reproduces: JSON-string root attrs, one-frame chunking, all-NaN ``stability_scale``
    at t=0, NaN ``time_scale[0]``, degenerate ``temperature``, ``pressure = density*c_s^2``.
    Velocity channel 0 is constant 1.0 and channel 1 constant 2.0 at t=0 so a channel-swap
    or an x/y transpose is detectable.

    The ``time`` dataset is chunked ``(1,)`` as the real solver writes it, which is what
    makes reading it in full expensive over HTTP. Pass ``times`` to write a deliberately
    non-uniform clock, which the affine reconstruction must refuse rather than smooth over.
    """
    n_spatial = len(shape)
    with h5py.File(path, "w") as f:
        f.attrs["discretization"] = json.dumps(
            {
                "spatial": {
                    "grid": list(shape),
                    "resolution": 1.0,
                    "length": [float(n) for n in shape],
                },
                "temporal": {
                    "grid": n_frames - 1,
                    "resolution": 1.0,
                    "length": float(n_frames - 1),
                },
            }
        )
        f.attrs["characteristic_scales"] = json.dumps(
            {"mass": 1, "length": 1.0, "time": 1.0, "temperature": 1}
        )
        f.attrs["units"] = json.dumps({"system": "dimensionless"})
        f.attrs["kinet_rollout_status"] = "complete"
        f.attrs["kinet_last_completed_step"] = np.int64(n_frames - 1)

        def make(name: str, n_channels: int, gen) -> None:
            data = np.empty((1, n_channels, n_frames, *shape), dtype=np.float64)
            for t in range(n_frames):
                data[0, :, t] = gen(t)
            f.create_dataset(
                name, data=data, chunks=(1, n_channels, 1, *shape)
            ).attrs["units"] = "-"

        density = {}

        def gen_density(t: int) -> np.ndarray:
            arr = 1.0 + 1e-3 * synthetic_field(shape, 1, seed=100 + t)
            density[t] = arr
            return arr

        make("density", 1, gen_density)
        # The solver writes rho * c_s^2, not rho / 3; those differ in the last ulp and
        # the fixture reproduces the real arithmetic.
        cs2 = np.float64(1.0) / np.float64(3.0)
        make("pressure", 1, lambda t: density[t] * cs2)

        def gen_velocity(t: int) -> np.ndarray:
            if t == 0:
                v = np.empty((n_spatial, *shape))
                for c in range(n_spatial):
                    v[c] = float(c + 1)  # u=1, v=2: catches channel swap and transpose
                return v
            return 0.04 * synthetic_field(shape, n_spatial, seed=200 + t)

        make("velocity", n_spatial, gen_velocity)
        make("vorticity", 1, lambda t: 0.01 * synthetic_field(shape, 1, seed=300 + t))
        make("F", 9, lambda t: np.abs(synthetic_field(shape, 9, seed=400 + t)) + 0.1)

        # All-NaN at t=0, finite after -- exactly as the real solver writes them.
        def gen_stability(t: int) -> np.ndarray:
            if t == 0:
                return np.full((1, *shape), np.nan)
            return np.full((1, *shape), 2.0)

        make("stability_scale", 1, gen_stability)
        make("stabilized_time_scale", 1, gen_stability)

        # Spatially degenerate: stored (1, 1, T, 1, 1).
        temp = np.full((1, 1, n_frames, *([1] * n_spatial)), 1.0 / 3.0)
        f.create_dataset("temperature", data=temp).attrs["units"] = "-"

        clock = _time_axis(n_frames) if times is None else np.asarray(times, dtype=np.float64)
        f.create_dataset("time", data=clock, chunks=(1,)).attrs["units"] = "-"
        f.create_dataset(
            "time_index", data=np.arange(n_frames, dtype=np.float64), chunks=(1,)
        ).attrs["units"] = "-"
        ts = np.full(n_frames, 0.5009)
        ts[0] = np.nan  # NaN at index 0, as in the real file
        f.create_dataset("time_scale", data=ts, chunks=(1,)).attrs["units"] = "-"
    return path


def write_well(path: Path, shape: tuple[int, int] = SHAPE,
               n_frames: int = N_FRAMES) -> Path:
    """Write a synthetic file in the PolymathicAI *Well* layout.

    Differs from raw kinet in three ways the reader must absorb: float32, no leading
    channel axis on scalars, and ``t1_fields/velocity`` is **channel-last**
    ``(1, T, *spatial, D)``. Velocity is u=1, v=2 at t=0, so a missed ``moveaxis`` shows up
    immediately.
    """
    with h5py.File(path, "w") as f:
        f.attrs["dataset_name"] = "synthetic"
        f.attrs["grid_type"] = "cartesian"
        f.attrs["n_spatial_dims"] = len(shape)
        f.attrs["n_trajectories"] = 1

        dims = f.create_group("dimensions")
        dims.attrs["spatial_dims"] = ["x", "y"]
        dims.create_dataset("time", data=_time_axis(n_frames))
        dims.create_dataset("x", data=np.arange(shape[0], dtype=np.float64))
        dims.create_dataset("y", data=np.arange(shape[1], dtype=np.float64))

        t0 = f.create_group("t0_fields")
        t0.attrs["field_names"] = ["density", "pressure", "vorticity"]
        dens = np.stack(
            [1.0 + 1e-3 * synthetic_field(shape, 1, seed=100 + t)[0]
             for t in range(n_frames)]
        )[None]
        t0.create_dataset("density", data=dens.astype(np.float32))
        t0.create_dataset("pressure", data=(dens / 3.0).astype(np.float32))
        vort = np.stack(
            [0.01 * synthetic_field(shape, 1, seed=300 + t)[0] for t in range(n_frames)]
        )[None]
        t0.create_dataset("vorticity", data=vort.astype(np.float32))

        t1 = f.create_group("t1_fields")
        t1.attrs["field_names"] = ["velocity"]
        vel = np.empty((1, n_frames, *shape, len(shape)), dtype=np.float32)
        for t in range(n_frames):
            if t == 0:
                for c in range(len(shape)):
                    vel[0, t, ..., c] = float(c + 1)
            else:
                v = 0.04 * synthetic_field(shape, len(shape), seed=200 + t)
                vel[0, t] = np.moveaxis(v, 0, -1)
        t1.create_dataset("velocity", data=vel)

        bc = f.create_group("boundary_conditions")
        for i, dim in enumerate(("x", "y")):
            g = bc.create_group(f"{dim}_periodic")
            g.attrs["bc_type"] = "PERIODIC"
            g.attrs["associated_dims"] = [dim]
            g.create_dataset("mask", data=np.zeros(shape[i], dtype=np.int8))
    return path
