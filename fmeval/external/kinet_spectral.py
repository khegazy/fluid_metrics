"""Spectral diagnostics vendored VERBATIM from the kinet repository.

Source: ``kinet/diagnostics/periodic_flow_diagnostics.py``
Repo:   https://github.com/khegazy/kinet
Commit: 454141e4915ca55c43ca7eee210ed180605ea96b
License: CC-BY-4.0 (declared in kinet's pyproject.toml). Attribution required.
Authors: Kareem Hegazy, Antonio Lara Benitez, Alex Kiefer, Yotam Yaniv,
         Maarten de Hoop, Michael Mahoney.

**Do not edit the functions below.** They are a byte-for-byte copy so the two
repositories cannot silently diverge; adapt behaviour in ``fmeval/derived.py``
instead. To re-sync, re-extract from the source path above and update the commit.

Why vendored rather than imported: ``import kinet`` pulls in
``kinet.runtime.distributed.fft``, which imports ``mpi4py``, which cannot load
libmpi on a Perlmutter login node. These diagnostics need only numpy, so a copy is
both lighter and more robust than the dependency.

Conventions carried over from the source, verified against the real data:

* Input velocity is ``(D, *grid)`` or ``(1, D, *grid)`` with ``D`` in {2, 3} and
  grid axes in x, y, z order -- the same layout this project uses.
* ``spectral_vorticity`` returns a bare ``(*grid)`` scalar in 2D and ``(3, *grid)``
  in 3D. ``fmeval.derived`` lifts the 2D case to ``(1, *grid)``.
* Wavenumbers are ``k_j = 2*pi*fftfreq(N_j, d=dx_j)``, so ``spacing`` must be the
  spacing of the grid actually being differentiated. It defaults to 1.0; passing a
  fine spacing at a coarse grid scales the result by exactly the coarsening factor.
* Periodic domains assumed. No dealiasing and no Nyquist zeroing are applied.

Validated here: reproduces the analytic Taylor-Green vorticity to 1.9e-14.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np

__all__ = [
    "divergence",
    "physical_wavenumber_grid",
    "spectral_derivative",
    "spectral_vorticity",
]


def _velocity_array(velocity) -> np.ndarray:
    """
    Normalize velocity to shape (D, *grid).

    Accepted inputs are one saved velocity field: (D, *grid) or (1, D, *grid).
    """
    velocity_np = (
        velocity.detach().cpu().numpy() if hasattr(velocity, "detach") else velocity
    )
    velocity_np = np.asarray(velocity_np).astype(np.float64, copy=False)
    if velocity_np.ndim >= 4 and velocity_np.shape[0] == 1:
        velocity_np = velocity_np[0]
    if velocity_np.ndim < 3 or velocity_np.shape[0] not in (2, 3):
        raise ValueError(
            "velocity must have shape (D, *grid) or (1, D, *grid); "
            f"got {velocity_np.shape}"
        )
    dim = int(velocity_np.shape[0])
    if velocity_np.ndim != dim + 1:
        raise ValueError(
            "velocity must contain one field with no time axis; expected "
            f"({dim}, *grid) with {dim} spatial axes, got {velocity_np.shape}"
        )
    return velocity_np

def _scalar_field_array(field) -> np.ndarray:
    """Normalize scalar fields to shape (*grid)."""
    field_np = field.detach().cpu().numpy() if hasattr(field, "detach") else field
    field_np = np.asarray(field_np).astype(np.float64, copy=False)
    while field_np.ndim >= 3 and field_np.shape[0] == 1:
        field_np = field_np[0]
    return field_np

def _fft_axes(grid_shape: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(range(len(grid_shape)))

def _spacing_values(
    grid_shape: Iterable[int], spacing: float | Iterable[float]
) -> list[float]:
    shape = tuple(int(n) for n in grid_shape)
    if np.isscalar(spacing):
        return [float(spacing)] * len(shape)
    values = [float(dx) for dx in spacing]
    if len(values) != len(shape):
        raise ValueError(f"spacing has length {len(values)}, expected {len(shape)}")
    return values

def physical_wavenumber_grid(
    grid_shape: Iterable[int], spacing: float | Iterable[float] = 1.0
) -> list[np.ndarray]:
    """
    Build physical wavenumber components for spectral derivatives.

    For a periodic scalar field ``f``, the spectral derivative is computed as

        d_j f = ifft(i k_j f_hat),

    with ``k_j = 2 pi fftfreq(N_j, d=dx_j)``. This is the standard Fourier
    differentiation convention for periodic DNS/post-processing; see Pope,
    DOI: https://doi.org/10.1017/CBO9780511840531.
    """
    shape = tuple(int(n) for n in grid_shape)
    spacing_values = _spacing_values(shape, spacing)

    k_1d = [
        2.0 * math.pi * np.fft.fftfreq(n, d=dx) for n, dx in zip(shape, spacing_values)
    ]
    return list(np.meshgrid(*k_1d, indexing="ij"))

def spectral_derivative(
    field,
    axis: int,
    *,
    spacing: float | Iterable[float] = 1.0,
) -> np.ndarray:
    """Differentiate a periodic scalar field spectrally."""
    field_np = _scalar_field_array(field)
    grid_shape = field_np.shape
    axes = _fft_axes(grid_shape)
    k_components = physical_wavenumber_grid(grid_shape, spacing)
    field_hat = np.fft.fftn(field_np, axes=axes)
    derivative_hat = 1j * k_components[axis] * field_hat
    return np.fft.ifftn(derivative_hat, axes=axes).real

def spectral_vorticity(
    velocity,
    *,
    spacing: float | Iterable[float] = 1.0,
) -> np.ndarray:
    """
    Compute vorticity spectrally.

    In 2D, ``omega = d_x u_y - d_y u_x`` is returned as a scalar field. In 3D,
    ``omega = curl(u)`` is returned as a vector field with shape ``(3, *grid)``.
    Vorticity-based invariants and balances follow standard incompressible
    turbulence notation; see Batchelor,
    DOI: https://doi.org/10.1017/CBO9780511800955.
    """
    velocity_np = _velocity_array(velocity)
    dim = velocity_np.shape[0]
    if dim == 2:
        return spectral_derivative(
            velocity_np[1], 0, spacing=spacing
        ) - spectral_derivative(velocity_np[0], 1, spacing=spacing)
    if dim == 3:
        ux, uy, uz = velocity_np
        omega_x = spectral_derivative(uz, 1, spacing=spacing) - spectral_derivative(
            uy, 2, spacing=spacing
        )
        omega_y = spectral_derivative(ux, 2, spacing=spacing) - spectral_derivative(
            uz, 0, spacing=spacing
        )
        omega_z = spectral_derivative(uy, 0, spacing=spacing) - spectral_derivative(
            ux, 1, spacing=spacing
        )
        return np.stack([omega_x, omega_y, omega_z], axis=0)
    raise ValueError(f"vorticity is implemented only for 2D/3D, got D={dim}")

def divergence(
    velocity,
    *,
    spacing: float | Iterable[float] = 1.0,
) -> np.ndarray:
    """Compute div(u) spectrally."""
    velocity_np = _velocity_array(velocity)
    dim = velocity_np.shape[0]
    div = np.zeros(velocity_np.shape[1:], dtype=np.float64)
    for axis in range(dim):
        div += spectral_derivative(velocity_np[axis], axis, spacing=spacing)
    return div
