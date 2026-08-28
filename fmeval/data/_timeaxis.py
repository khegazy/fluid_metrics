"""Reading a trajectory's clock without reading the whole file.

The cost of `f["time"][:]` is a property of the **chunking**, not of the slice, and the two
formats this repository reads sit on opposite sides of it. Measured 2026-08-27 against the
published production trajectory:

* raw kinet, ``time``: ``chunks=(1,)`` -- 10001 chunks of eight bytes each, interleaved
  17.8 MiB apart across the 166 GiB file, because the solver appends one clock value per
  frame beside that frame's payload. Over HTTP, ``ds[:]`` is **9938 requests, 297 s and
  2.5 GiB** to retrieve 80 KB. Locally the page cache hides it.
* Well, ``dimensions/time``: ``chunks=None``, contiguous, 80008 bytes at offset 8192. Over
  HTTP that is **one 80 KB range GET**. Nothing to fix.

So the discriminator is `ds.chunks`, which is free and exact, and a local read is never
changed at all. For the remaining case -- remote and chunked -- the axis is reconstructed
as an affine ramp and then *verified* against sampled elements. On both the production and
the dev file ``time[:] == arange(n) * dt`` is bitwise exact (``np.array_equal``, not
``allclose``), but that is a property of how the solver wrote them rather than a guarantee,
so it is checked rather than believed.

The result is always a real ``np.ndarray``: the ``Trajectory.times`` contract is unchanged,
and ``np.diff``, ``np.isfinite``, ``len()`` and slicing all keep working as before.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

TimeAxisMode = Literal["auto", "affine", "read"]

#: Endpoints plus this many interior samples are checked against the reconstruction.
DEFAULT_SPOT_CHECKS = 8


class NonUniformTimeAxis(ValueError):
    """A chunked remote clock is not the affine ramp its endpoints imply."""


def read_time_axis(
    ds,
    *,
    remote: bool,
    mode: TimeAxisMode = "auto",
    spot_checks: int = DEFAULT_SPOT_CHECKS,
) -> np.ndarray:
    """Materialise the physical time of every frame.

    Args:
        ds: The 1-D HDF5 dataset holding the clock.
        remote: Whether the file is being read over HTTP.
        mode: ``"auto"`` reads directly unless the axis is both remote and chunked;
            ``"read"`` always reads it in full, at the cost above; ``"affine"`` always
            reconstructs, for a local file whose clock is chunked the same way.
        spot_checks: Interior samples used to verify a reconstruction.

    Returns:
        The clock, shape ``(T,)``, float64.

    Raises:
        NonUniformTimeAxis: If a reconstruction disagrees with the stored values.
    """
    n = int(ds.shape[0])  # object-header metadata: free, no data read
    if mode == "read" or n == 0:
        return np.asarray(ds[:], dtype=np.float64)
    if mode == "auto" and not (remote and ds.chunks is not None):
        return np.asarray(ds[:], dtype=np.float64)
    return _affine_axis(ds, n, spot_checks)


def _affine_axis(ds, n: int, spot_checks: int) -> np.ndarray:
    """Reconstruct from the first two samples, then verify against the stored values."""
    first = float(ds[0])
    if n == 1:
        return np.asarray([first], dtype=np.float64)

    step = float(ds[1]) - first
    if not np.isfinite(step) or step <= 0.0:
        raise NonUniformTimeAxis(
            f"the clock does not advance: time[0]={first!r}, time[1]={float(ds[1])!r}. "
            "A trajectory's time axis must be strictly increasing."
        )

    ramp = np.arange(n, dtype=np.float64) * step
    # `first` is 0.0 in every file measured, and `arange*dt` reproduces those bitwise;
    # adding a zero offset would not, in general, be a no-op for other files, so it is
    # only applied when it is actually needed.
    axis = ramp if first == 0.0 else first + ramp

    for index in _sample_indices(n, spot_checks):
        stored = float(ds[index])
        if stored != axis[index]:
            raise NonUniformTimeAxis(
                f"time[{index}] is {stored!r}, but the ramp implied by time[0] and "
                f"time[1] gives {float(axis[index])!r} (step {step!r}).\n"
                "This clock is not uniform, so it cannot be reconstructed. Reading it in "
                "full is correct but expensive on a chunked remote file -- measured 297 s "
                "and 2.5 GiB on the 166 GiB production trajectory. To do it anyway, pass "
                "`reader.time_axis=read` in the dataset config."
            )
    return axis


def _sample_indices(n: int, spot_checks: int) -> list[int]:
    """Both endpoints, the second element, and an even interior spread. Deterministic."""
    wanted = {0, 1, n - 1}
    if spot_checks > 0:
        wanted.update(int(i) for i in np.linspace(0, n - 1, spot_checks + 2))
    return sorted(i for i in wanted if 0 <= i < n)
