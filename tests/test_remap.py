"""IN-2 remap and derived-field recomputation.

The properties pinned here are the ones whose violation is silent: conservation, spacing
scaling, and the primitive/derived split. A broken remap still produces plausible pictures.
"""

from __future__ import annotations

import numpy as np
import pytest

from fmeval.data.base import GridSpec
from fmeval.derived import (
    CS2,
    pressure_from_density,
    recompute_frame,
    vorticity_from_velocity,
)
from fmeval.external.kinet_spectral import spectral_vorticity
from fmeval.remap import block_average, coarsen_factor, remap_frame, subsample
from tests.conftest import synthetic_field


def grid_for(shape, spacing=1.0) -> GridSpec:
    n = len(shape)
    return GridSpec(
        shape=tuple(shape),
        spacing=(spacing,) * n,
        periodic=(True,) * n,
        dims=("x", "y", "z")[:n],
        origin=(0.0,) * n,
    )


# --- block_average ------------------------------------------------------------------


@pytest.mark.parametrize("shape", [(16, 8), (16, 8, 4), (16,)])
def test_block_average_is_dimension_agnostic(shape):
    x = synthetic_field(shape, 2, seed=0)
    out = block_average(x, 2)
    assert out.shape == (2, *[n // 2 for n in shape])


def test_block_average_matches_handwritten_2d():
    """Guard the reshape arithmetic against a version written out longhand."""
    x = synthetic_field((16, 8), 2, seed=0)
    c, nx, ny = x.shape
    want = x.reshape(c, nx // 2, 2, ny // 2, 2).mean(axis=(2, 4))
    assert np.array_equal(block_average(x, 2), want)


@pytest.mark.parametrize("factor", [2, 4, 8])
def test_block_average_preserves_the_mean(factor):
    x = synthetic_field((16, 8), 1, seed=0)
    assert block_average(x, factor).mean() == pytest.approx(x.mean(), abs=1e-15)


def test_block_average_is_idempotent():
    """Coarsening twice by 2 must equal coarsening once by 4, bitwise."""
    x = synthetic_field((16, 8), 1, seed=0)
    assert np.allclose(block_average(block_average(x, 2), 2), block_average(x, 4),
                       rtol=0, atol=1e-15)


def test_block_average_factor_one_is_identity():
    x = synthetic_field((16, 8), 2, seed=0)
    assert block_average(x, 1) is x


def test_non_dividing_factor_raises_rather_than_truncating():
    x = synthetic_field((16, 8), 1, seed=0)
    with pytest.raises(ValueError, match="does not divide"):
        block_average(x, 3)


def test_block_average_differs_from_subsample_on_structured_data():
    """The conservative/aliasing distinction must be real, not nominal.

    Block averaging removes small-scale variance; subsampling folds it back in.
    """
    x = synthetic_field((16, 8), 1, seed=0, noise=0.3)
    ba, ss = block_average(x, 4), subsample(x, 4)
    assert not np.allclose(ba, ss)
    assert ba.var() < x.var(), "averaging should remove small-scale variance"
    assert ss.var() > ba.var(), "subsampling should alias variance back in"


# --- factor resolution ---------------------------------------------------------------


def test_coarsen_factor():
    g = grid_for((256, 256))
    assert coarsen_factor(g, None) == 1
    assert coarsen_factor(g, 256) == 1
    assert coarsen_factor(g, 64) == 4
    with pytest.raises(ValueError, match="finer than the data"):
        coarsen_factor(g, 512)
    with pytest.raises(ValueError, match="does not divide"):
        coarsen_factor(g, 100)


# --- spectral vorticity --------------------------------------------------------------


def test_taylor_green_vorticity_is_analytic():
    """kinet's own acceptance test, ported: omega = 2 sin x sin y."""
    n, length = 64, 2 * np.pi
    dx = length / n
    x = np.arange(n) * dx
    xx, yy = np.meshgrid(x, x, indexing="ij")  # axis 0 == x, axis 1 == y
    u = np.stack([np.sin(xx) * np.cos(yy), -np.cos(xx) * np.sin(yy)])
    omega = vorticity_from_velocity(u, grid_for((n, n), dx))
    assert omega.shape == (1, n, n), "2D vorticity must be lifted to a channel axis"
    assert np.abs(omega[0] - 2 * np.sin(xx) * np.sin(yy)).max() < 1e-12


def test_vorticity_spacing_scales_the_result_by_exactly_the_factor():
    """Passing fine spacing at a coarse grid is a silent factor-f error. Pin it."""
    x = synthetic_field((32, 32), 2, seed=0)
    coarse = block_average(x, 4)
    right = spectral_vorticity(coarse, spacing=[4.0, 4.0])
    wrong = spectral_vorticity(coarse, spacing=[1.0, 1.0])
    assert np.allclose(wrong, 4.0 * right, rtol=1e-10)


def test_vorticity_rejects_a_mismatched_grid():
    u = synthetic_field((16, 8), 2, seed=0)
    with pytest.raises(ValueError, match="does not match grid"):
        vorticity_from_velocity(u, grid_for((8, 8)))


def test_vorticity_rejects_a_nonperiodic_grid():
    u = synthetic_field((16, 8), 2, seed=0)
    g = GridSpec((16, 8), (1.0, 1.0), (True, False), ("x", "y"), (0.0, 0.0))
    with pytest.raises(ValueError, match="periodic"):
        vorticity_from_velocity(u, g)


def test_pressure_equation_of_state():
    rho = 1.0 + 1e-3 * synthetic_field((16, 8), 1, seed=0)
    assert np.array_equal(pressure_from_density(rho), rho * CS2)
    assert CS2 == pytest.approx(1 / 3)


# --- the primitive / derived split ---------------------------------------------------


def _frame(shape=(32, 32), spacing=1.0):
    from fmeval.data.base import Frame

    grid = grid_for(shape, spacing)
    fields = {
        "density": 1.0 + 1e-3 * synthetic_field(shape, 1, seed=1),
        "velocity": 0.04 * synthetic_field(shape, 2, seed=2),
    }
    fields["vorticity"] = vorticity_from_velocity(fields["velocity"], grid)
    return Frame(index=0, time=0.0, fields=fields, grid=grid)


def test_remap_recomputes_vorticity_rather_than_averaging_it():
    """The correction this module exists for. If these ever agree, something regressed."""
    frame = _frame()
    remapped = remap_frame(frame, 4)
    averaged = block_average(frame["vorticity"], 4)
    recomputed = remapped["vorticity"]

    assert recomputed.shape == averaged.shape
    rel = np.sqrt(((recomputed - averaged) ** 2).mean()) / averaged.std()
    assert rel > 0.02, (
        f"recomputed and block-averaged vorticity differ by only {rel:.1%}; the "
        "derived-field path may have regressed to plain averaging"
    )
    # It must be the curl of the REMAPPED velocity, on the coarse grid.
    want = vorticity_from_velocity(remapped["velocity"], remapped.grid)
    assert np.allclose(recomputed, want, rtol=1e-12)


def test_remap_scales_grid_spacing():
    frame = _frame(spacing=0.5)
    remapped = remap_frame(frame, 4)
    assert remapped.grid.shape == (8, 8)
    assert remapped.grid.spacing == (2.0, 2.0)
    assert remapped.grid.length == frame.grid.length


def test_remap_averages_primitives():
    frame = _frame()
    remapped = remap_frame(frame, 2)
    assert np.array_equal(remapped["density"], block_average(frame["density"], 2))
    assert np.array_equal(remapped["velocity"], block_average(frame["velocity"], 2))


def test_remap_factor_one_is_identity():
    frame = _frame()
    assert remap_frame(frame, 1) is frame


def test_remap_falls_back_to_averaging_without_the_primitive():
    """Derived-without-inputs must degrade gracefully, not raise."""
    from fmeval.data.base import Frame

    grid = grid_for((16, 8))
    vort = synthetic_field((16, 8), 1, seed=3)
    frame = Frame(index=0, time=0.0, fields={"vorticity": vort}, grid=grid)
    out = remap_frame(frame, 2)
    assert np.array_equal(out["vorticity"], block_average(vort, 2))


def test_recompute_frame_puts_the_native_grid_on_the_same_operator():
    """Stored vorticity must be replaceable so native and coarse grids are comparable."""
    from fmeval.data.base import Frame

    grid = grid_for((32, 32))
    stored = synthetic_field((32, 32), 1, seed=9)  # pretend: a lattice-stencil vorticity
    vel = 0.04 * synthetic_field((32, 32), 2, seed=2)
    frame = Frame(0, 0.0, {"velocity": vel, "vorticity": stored}, grid)
    out = recompute_frame(frame)
    assert not np.allclose(out["vorticity"], stored)
    assert np.allclose(out["vorticity"], vorticity_from_velocity(vel, grid))
    assert np.array_equal(out["velocity"], vel), "primitives must be untouched"
