"""IN-2: conservative remapping onto a common analysis grid.

Every frame passes through this before any metric sees it. At the native resolution the
remap is the identity, so a same-grid run is unaffected -- but it means comparing a 128^2
prediction against a 256^2 reference is a config value rather than a code change, and the
analysis resolution is recorded alongside every number instead of being implicit.

The operator is a **conservative block average by an integer factor**: for factor ``f``,
average over non-overlapping ``f x f`` boxes, box side equal to the compression factor.
So 256 -> 128 uses 2x2 boxes, 256 -> 64 uses 4x4, and so on down the chain
128, 64, 32, 16, 8.

Three things make this IN-2 rather than plain downsampling:

1. **Cell averages, not point samples.** Point-sampling every f-th cell aliases small
   scales into large ones and is not conservative. Measured on the real 256^2 vorticity
   field at f=8, block averaging retains 73% of the variance while subsampling retains
   102% -- subsampling folds small-scale energy back in rather than removing it. The
   ``subsample`` degradation exists so that difference is measurable, not asserted.
2. **The remapping operator is part of the metric definition.** ``analysis_grid`` and
   ``remap_op`` become columns in the result frame, so a number is never separated from
   the grid it was computed on.
3. **Derived fields are recomputed, not averaged.** Vorticity is the curl of velocity;
   block-averaging it gives a field that is not the vorticity of the coarse velocity.
   See :mod:`fmeval.derived`, which this module calls.

Verified on the real data: the global mean is preserved to machine precision at every
factor, coarsening twice by 2 is bitwise identical to coarsening once by 4, and the
dimension-agnostic form matches a hand-written 2D version on a non-square array.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

from .data.base import FIELDS, Frame, GridSpec

RemapMethod = Literal["block_mean", "subsample"]


def block_average(x: np.ndarray, factor: int) -> np.ndarray:
    """Conservative coarsening: mean over non-overlapping ``factor``-sided boxes.

    Exact for cell-averaged quantities on a uniform Cartesian grid, where the arithmetic
    mean of equal-area cell averages *is* the coarse cell average.

    Args:
        x: Array of shape ``(C, *spatial)`` with any number of spatial dimensions.
        factor: Compression factor; the box side length. Must divide every spatial extent.

    Returns:
        Array of shape ``(C, *[n // factor for n in spatial])``.

    Raises:
        ValueError: If ``factor`` does not divide every spatial extent, rather than
            silently truncating.
    """
    if factor < 1:
        raise ValueError(f"factor must be >= 1, got {factor}")
    if factor == 1:
        return x
    n_channels, *spatial = x.shape
    if any(n % factor for n in spatial):
        raise ValueError(f"factor {factor} does not divide grid {tuple(spatial)}")

    shape: list[int] = [n_channels]
    box_axes: list[int] = []
    for i, n in enumerate(spatial):
        shape += [n // factor, factor]
        box_axes.append(2 + 2 * i)  # the within-box axis for this dimension
    return x.reshape(shape).mean(axis=tuple(box_axes))


def subsample(x: np.ndarray, factor: int) -> np.ndarray:
    """Non-conservative coarsening: keep every ``factor``-th cell.

    The control against which :func:`block_average` is judged. Aliases small scales into
    large ones, which is exactly the failure IN-2's "compare cell averages" rule avoids.
    """
    if factor < 1:
        raise ValueError(f"factor must be >= 1, got {factor}")
    if factor == 1:
        return x
    n_channels, *spatial = x.shape
    if any(n % factor for n in spatial):
        raise ValueError(f"factor {factor} does not divide grid {tuple(spatial)}")
    slicer = (slice(None),) + tuple(slice(None, None, factor) for _ in spatial)
    return x[slicer]


_METHODS = {"block_mean": block_average, "subsample": subsample}


def coarsen_factor(grid: GridSpec, target_resolution: int | None) -> int:
    """The integer factor taking ``grid`` to a target resolution along its first axis.

    Args:
        grid: The native grid.
        target_resolution: Desired extent along the first spatial axis, or None for no
            change.

    Raises:
        ValueError: If the target is larger than the native grid (we never upsample -- a
            metric cannot invent information), or does not divide it evenly.
    """
    if target_resolution is None:
        return 1
    native = grid.shape[0]
    if target_resolution == native:
        return 1
    if target_resolution > native:
        raise ValueError(
            f"analysis grid {target_resolution} is finer than the data ({native}); "
            "upsampling would invent information"
        )
    if native % target_resolution:
        raise ValueError(
            f"analysis grid {target_resolution} does not divide the native grid {native}"
        )
    return native // target_resolution


def remap_frame(
    frame: Frame,
    factor: int,
    *,
    method: RemapMethod = "block_mean",
    recompute_derived: bool = True,
) -> Frame:
    """Remap every field of a frame onto a coarser analysis grid.

    Primitive fields are averaged (or subsampled); derived fields are **recomputed** from
    the remapped primitives when their inputs are present, and averaged only as a
    documented fallback when they are not.

    Args:
        frame: The frame to remap.
        factor: Integer coarsening factor; 1 is the identity.
        method: ``"block_mean"`` (conservative, the default) or ``"subsample"``.
        recompute_derived: Recompute derived fields rather than averaging them. Leave
            True; False exists only so the difference can be measured.

    Returns:
        A new Frame on the coarsened grid. The input is returned unchanged when
        ``factor == 1``.
    """
    if factor == 1:
        return frame
    from .derived import recompute, recomputable

    op = _METHODS[method]
    grid = frame.grid.coarsened(factor)

    out: dict[str, np.ndarray] = {}
    deferred: list[str] = []
    for name, arr in frame.fields.items():
        if recompute_derived and FIELDS[name].kind == "derived":
            deferred.append(name)
            continue
        out[name] = op(arr, factor)

    for name in deferred:
        if recomputable(name, out):
            out[name] = recompute(name, out, grid)
        else:
            # No inputs to recompute from. Averaging a derived field is wrong in
            # principle (see fmeval.derived), so this is a fallback, not a default.
            out[name] = op(frame.fields[name], factor)

    members = None
    if frame.has_members:
        # Every member is remapped exactly as the reference is, one member at a time so
        # that the recompute-rather-than-average rule for derived fields applies within
        # each member. Block-averaging a member's vorticity would leave a field that is
        # not the curl of the velocity beside it, and doing that N times does not make it
        # right.
        names = list(frame.members)
        n_members = frame.members[names[0]].shape[0]
        per_member = [
            remap_frame(
                Frame(
                    index=frame.index,
                    time=frame.time,
                    fields={name: frame.members[name][i] for name in names},
                    grid=frame.grid,
                ),
                factor,
                method=method,
                recompute_derived=recompute_derived,
            ).fields
            for i in range(n_members)
        ]
        members = {
            name: np.stack([fields[name] for fields in per_member]) for name in names
        }

    return frame.with_fields(out, grid, members=members)
