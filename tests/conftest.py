"""Shared fixtures.

Two conventions here are load-bearing and deliberate:

**Fields are non-square.** Every synthetic grid is 16x8, never 16x16. kinet stores data as
``(C, X, Y, Z)`` and every real dataset is square (256^2, 512^2), so a reader or operator
that transposes X and Y passes every test on square data and produces silently wrong
pictures forever. Non-square fixtures are the only place that bug can be caught.

**Fields have real structure.** A field of pure noise makes blur, coarsening and low-pass
indistinguishable, so the synthetic field is a two-scale sine plus a seeded noise floor:
smoothing operators bite the small scale first, which is what makes a synthetic
degradation ladder monotone the way a real one is.
"""

from __future__ import annotations

import numpy as np
import pytest

#: Deliberately non-square. See the module docstring.
GRID: tuple[int, int] = (16, 8)


def synthetic_field(
    shape: tuple[int, ...] = GRID,
    n_channels: int = 1,
    *,
    seed: int = 0,
    noise: float = 0.05,
) -> np.ndarray:
    """A periodic, two-scale, mildly noisy field of shape ``(n_channels, *shape)``.

    Args:
        shape: Spatial extents, in ``(x, y[, z])`` order.
        n_channels: Number of channels; each gets a different phase offset.
        seed: RNG seed for the noise floor.
        noise: Noise amplitude relative to the deterministic part.

    Returns:
        Array of shape ``(n_channels, *shape)``, float64, periodic on every axis.
    """
    rng = np.random.default_rng(seed)
    coords = np.meshgrid(
        *[2 * np.pi * np.arange(n) / n for n in shape], indexing="ij"
    )
    out = np.empty((n_channels, *shape), dtype=np.float64)
    for c in range(n_channels):
        phase = 0.7 * c
        large = np.sin(coords[0] + phase)
        small = 0.35 * np.cos(4 * coords[0] + phase)
        for axis in coords[1:]:
            large = large * np.cos(axis + phase)
            small = small + 0.35 * np.sin(3 * axis + phase)
        out[c] = large + small + noise * rng.standard_normal(shape)
    return out


@pytest.fixture
def field() -> np.ndarray:
    """Single-channel non-square field, ``(1, 16, 8)``."""
    return synthetic_field(GRID, 1, seed=0)


@pytest.fixture
def field2() -> np.ndarray:
    """A *different* single-channel field, for symmetry and ordering checks."""
    return synthetic_field(GRID, 1, seed=1)


@pytest.fixture
def vector_field() -> np.ndarray:
    """Two-channel non-square field, ``(2, 16, 8)`` — stands in for velocity."""
    return synthetic_field(GRID, 2, seed=2)
