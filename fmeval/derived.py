"""Recomputation of derived fields from their primitives.

**Vorticity cannot be block-averaged like the other observables.** It is the curl of the
velocity, so the coarse-grid vorticity has to be recomputed from the coarse-grid velocity.
Otherwise the "vorticity" on the analysis grid is not the vorticity of the velocity field
on that grid, and every vorticity diagnostic becomes inconsistent with the velocity it is
supposed to describe.

How much this matters, measured on the real 256^2 frame at t=5000 -- recomputed vorticity
against the naive block-averaged vorticity:

===========  ====================
factor       rms relative difference
===========  ====================
2            5.6%
4            18.3%
8            25.9%
===========  ====================

Not a rounding detail, and it grows with exactly the coarsening the analysis grid is for.

Two rules that keep this honest:

**The spacing must be the coarse spacing.** ``dx_coarse = factor * dx_fine``. The vendored
kinet function defaults to ``spacing=1.0``; passing the fine spacing at a coarse grid
inflates the vorticity by *exactly* the factor -- verified at 2x, 4x and 8x. Nothing here
lets the default apply: spacing always comes from the :class:`GridSpec`.

**Never mix a stored derived field with a recomputed one.** The kinet solver wrote
``vorticity`` with a D2Q9 lattice stencil, not a spectral derivative; measured against the
spectral result on the native grid they differ by 8.1% rms (correlation 0.997). Both are
defensible discretisations, but using the stored field at 256^2 and a spectral one at
128^2 would make the grid-independence criterion measure operator mismatch rather than
grid effects. So derived fields are recomputed with *our* operator at every analysis grid,
including the native one; the stored field is only ever read as a cross-check.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from .data.base import FIELDS, Frame, GridSpec
from .external.kinet_spectral import spectral_vorticity

#: Isothermal D2Q9 lattice sound speed squared. The solver writes ``pressure = rho * c_s^2``
#: (bitwise, verified at t = 1, 5000, 10000), which differs from ``rho / 3`` by one ulp.
CS2: float = float(np.float64(1.0) / np.float64(3.0))

#: Derived field -> the primitives it is computed from.
RECIPES: dict[str, tuple[str, ...]] = {
    "vorticity": ("velocity",),
    "pressure": ("density",),
}


def recomputable(name: str, available: Mapping[str, np.ndarray]) -> bool:
    """Whether ``name`` can be recomputed from the fields present in ``available``."""
    inputs = RECIPES.get(name)
    return inputs is not None and all(i in available for i in inputs)


def vorticity_from_velocity(velocity: np.ndarray, grid: GridSpec) -> np.ndarray:
    """Spectral curl of the velocity, on ``grid``.

    Args:
        velocity: ``(D, *spatial)`` with D == grid.n_spatial.
        grid: The grid the velocity lives on. Its spacing is what sets the wavenumbers,
            so this must be the *analysis* grid, not the native one.

    Returns:
        ``(1, *spatial)`` in 2D and ``(3, *spatial)`` in 3D -- the 2D scalar is lifted to a
        channel axis so it matches the canonical ``(C, *spatial)`` layout, exactly as
        kinet's own ``compute_vorticity_slab`` does.
    """
    if velocity.shape[0] != grid.n_spatial:
        raise ValueError(
            f"velocity has {velocity.shape[0]} components but the grid is "
            f"{grid.n_spatial}-dimensional"
        )
    if velocity.shape[1:] != grid.shape:
        raise ValueError(
            f"velocity spatial shape {velocity.shape[1:]} does not match grid {grid.shape}"
        )
    if not all(grid.periodic):
        raise ValueError(
            "spectral vorticity assumes a fully periodic domain; this grid is "
            f"periodic={grid.periodic}"
        )
    # spacing=grid.spacing is the whole point: at a coarse grid the fine spacing would
    # scale the result by the coarsening factor.
    omega = spectral_vorticity(velocity, spacing=list(grid.spacing))
    return omega[np.newaxis, ...] if omega.ndim == grid.n_spatial else omega


def pressure_from_density(density: np.ndarray) -> np.ndarray:
    """Equation of state for the isothermal D2Q9 solver: ``p = rho * c_s^2``."""
    return density * CS2


def recompute(
    name: str, fields: Mapping[str, np.ndarray], grid: GridSpec
) -> np.ndarray:
    """Recompute one derived field from primitives already on ``grid``.

    Raises:
        KeyError: If ``name`` has no recipe or a required primitive is missing.
    """
    inputs = RECIPES.get(name)
    if inputs is None:
        raise KeyError(f"no recipe for derived field {name!r}")
    missing = [i for i in inputs if i not in fields]
    if missing:
        raise KeyError(f"cannot recompute {name!r}: missing {missing}")

    if name == "vorticity":
        return vorticity_from_velocity(fields["velocity"], grid)
    if name == "pressure":
        return pressure_from_density(fields["density"])
    raise KeyError(f"no implementation for derived field {name!r}")


def recompute_frame(frame: Frame, names: tuple[str, ...] | None = None) -> Frame:
    """Return a copy of ``frame`` with derived fields recomputed from its primitives.

    Used to put the *native* grid on the same footing as every coarse grid, so a
    grid-independence sweep compares like with like rather than a lattice-stencil
    vorticity against a spectral one.

    Args:
        frame: Frame whose derived fields should be replaced.
        names: Which derived fields to recompute. Defaults to every derived field present
            that has its inputs available.
    """
    targets = names or tuple(
        n for n in frame.fields
        if FIELDS[n].kind == "derived" and recomputable(n, frame.fields)
    )
    if not targets:
        return frame
    out = dict(frame.fields)
    for name in targets:
        out[name] = recompute(name, frame.fields, frame.grid)
    return frame.with_fields(out, frame.grid)
