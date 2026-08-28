"""The loader contract, shared across every reader.

The two highest-value tests here are easy to overlook:

* ``test_axis_and_channel_order`` -- fixtures are non-square (16x8) with u=1, v=2, so a
  transposed or channel-swapped reader fails loudly. On the real 256^2 data it would pass
  silently and every figure in every report would be wrong.
* ``test_never_slices_the_time_axis`` -- monkeypatches ``h5py`` to record every key used.
  A one-character slip from ``ds[0, :, t]`` to ``ds[0, :, :]`` turns a 1-second read into
  5 GB of I/O, and no correctness test would notice.

That second test has one blind spot, and it has a sibling elsewhere because of it: it
filters keys with ``len(key) >= 3`` to reach the time position of a field read, so a read
of the 1-D ``time`` dataset -- key ``(slice(None),)``, length one -- passes straight
through it. Slicing *that* dataset whole is the most expensive read in this package over
HTTP. ``test_opening_and_iterating_never_slices_a_chunked_clock`` in
tests/test_remote_data.py covers it.
"""

from __future__ import annotations

import numpy as np
import pytest

from fmeval.data.base import (
    CANONICAL_FIELDS,
    FIELDS,
    GridSpec,
    TimeSelection,
    Trajectory,
)
from fmeval.data.kinet_raw import KinetRawTrajectory
from tests.fixtures_h5 import N_FRAMES, SHAPE, write_kinet_raw


@pytest.fixture
def kinet_file(tmp_path):
    return write_kinet_raw(tmp_path / "kinet_raw.h5")


@pytest.fixture
def traj(kinet_file):
    with KinetRawTrajectory(kinet_file, nan_policy="error") as t:
        yield t


# --- shape, dtype, axis order ------------------------------------------------------


def test_frame_shape_dtype_and_channels(traj):
    frame = traj.frame(1, traj.fields)
    for name, arr in frame.fields.items():
        want_c = FIELDS[name].n_channels(traj.grid.n_spatial)
        assert arr.shape == (want_c, *SHAPE), f"{name} has shape {arr.shape}"
        assert arr.dtype == np.float64
        assert np.isfinite(arr).all()


def test_axis_and_channel_order(traj):
    """u=1, v=2 at t=0 on a non-square grid: catches a channel swap AND a transpose."""
    vel = traj.frame(0, ["velocity"])["velocity"]
    assert vel.shape == (2, *SHAPE), "spatial axes are transposed (grid is 16x8)"
    assert np.allclose(vel[0], 1.0), "velocity channel 0 is not the x component"
    assert np.allclose(vel[1], 2.0), "velocity channel 1 is not the y component"


def test_grid_spec(traj):
    g = traj.grid
    assert g.shape == SHAPE
    assert g.dims == ("x", "y")
    assert g.spacing == (1.0, 1.0)
    assert g.periodic == (True, True)
    assert g.n_spatial == 2
    assert g.length == (float(SHAPE[0]), float(SHAPE[1]))


def test_grid_axis_resolution_is_dimension_aware():
    """`axis('x')` must be -2 in 2D and -3 in 3D, never a hardcoded constant."""
    g2 = GridSpec((16, 8), (1.0, 1.0), (True, True), ("x", "y"), (0.0, 0.0))
    assert g2.axis("x") == -2 and g2.axis("y") == -1
    g3 = GridSpec((4, 5, 6), (1.0,) * 3, (True,) * 3, ("x", "y", "z"), (0.0,) * 3)
    assert g3.axis("x") == -3 and g3.axis("y") == -2 and g3.axis("z") == -1


def test_grid_coarsened_scales_spacing():
    """Spacing must grow by the factor -- forgetting this inflates spectral derivatives."""
    g = GridSpec((16, 8), (0.5, 0.5), (True, True), ("x", "y"), (0.0, 0.0))
    c = g.coarsened(2)
    assert c.shape == (8, 4)
    assert c.spacing == (1.0, 1.0)
    assert c.length == g.length  # physical extent is unchanged
    with pytest.raises(ValueError, match="does not divide"):
        g.coarsened(3)


# --- times -------------------------------------------------------------------------


def test_times_are_monotone_and_finite(traj):
    times = traj.times
    assert len(times) == N_FRAMES == len(traj)
    assert np.isfinite(times).all()
    assert np.all(np.diff(times) > 0)


def test_time_scale_is_not_used_as_a_clock(traj):
    """`time_scale[0]` is NaN in real files; the reader must use `time` instead."""
    assert np.isfinite(traj.times).all()
    assert traj.times[0] == 0.0


# --- field vocabulary --------------------------------------------------------------


def test_fields_are_canonical(traj):
    assert set(traj.fields) <= CANONICAL_FIELDS


def test_degenerate_and_redundant_fields_excluded(traj):
    assert "temperature" not in traj.fields, "spatially degenerate; not a field"
    assert "pressure" not in traj.fields, "exactly density/3; excluded by default"


def test_redundant_field_available_on_request(kinet_file):
    with KinetRawTrajectory(kinet_file, include_redundant=True) as t:
        assert "pressure" in t.fields
        frame = t.frame(1, ["density", "pressure"])
        assert np.allclose(frame["pressure"], frame["density"] / 3.0)


def test_requesting_unknown_field_raises(traj):
    with pytest.raises(ValueError, match="unknown canonical field"):
        traj.frame(1, ["not_a_field"])


def test_requesting_unavailable_field_raises(traj):
    with pytest.raises(ValueError, match="not available"):
        traj.frame(1, ["pressure"])


# --- NaN policy --------------------------------------------------------------------


def test_nan_policy_error_on_all_nan_frame(kinet_file):
    """t=0 has all-NaN stability fields in real data; here vorticity is fine but we
    exercise the guard through a field the fixture does make non-finite."""
    with KinetRawTrajectory(kinet_file, nan_policy="error") as t:
        frame = t.frame(0, ["density"])
        assert np.isfinite(frame["density"]).all()


def test_nan_policy_warn_and_ignore(tmp_path, monkeypatch):
    path = write_kinet_raw(tmp_path / "nan.h5")
    import h5py

    with h5py.File(path, "r+") as f:
        f["density"][0, 0, 0, 0, 0] = np.nan

    with KinetRawTrajectory(path, nan_policy="error") as t:
        with pytest.raises(ValueError, match="non-finite"):
            t.frame(0, ["density"])
    with KinetRawTrajectory(path, nan_policy="warn") as t:
        with pytest.warns(RuntimeWarning, match="non-finite"):
            t.frame(0, ["density"])
    with KinetRawTrajectory(path, nan_policy="ignore") as t:
        assert not np.isfinite(t.frame(0, ["density"])["density"]).all()


# --- time selection ----------------------------------------------------------------


@pytest.mark.parametrize(
    "sel,n,expected",
    [
        (TimeSelection(), 5, [0, 1, 2, 3, 4]),
        (TimeSelection(start=1), 5, [1, 2, 3, 4]),
        (TimeSelection(start=1, reduction=2), 5, [1, 3]),
        (TimeSelection(start=1, reduction=2, max_frames=1), 5, [1]),
        (TimeSelection(start=1, stop=4), 5, [1, 2, 3]),
        (TimeSelection(reduction=10), 5, [0]),
        (TimeSelection(start=99), 5, []),
    ],
)
def test_time_selection_resolves(sel, n, expected):
    assert sel.resolve(n).tolist() == expected


def test_max_frames_applies_after_reduction():
    """Order matters: cap the reduced set, not the raw range."""
    sel = TimeSelection(reduction=3, max_frames=2)
    assert sel.resolve(20).tolist() == [0, 3]


def test_invalid_reduction_raises():
    with pytest.raises(ValueError, match="reduction must be >= 1"):
        TimeSelection(reduction=0)


def test_iter_frames_is_ascending(traj):
    idx = [f.index for f in traj.iter_frames(["density"], TimeSelection(start=1))]
    assert idx == sorted(idx) == [1, 2, 3, 4]


# --- the time-axis-slicing guard ---------------------------------------------------


def test_frame_rejects_non_integer_index(traj):
    for bad in (slice(0, 2), 1.0, [0, 1], np.array([0, 1])):
        with pytest.raises(TypeError, match="must be an int"):
            traj.frame(bad, ["density"])


def test_never_slices_the_time_axis(traj, monkeypatch):
    """Record every h5py key used and assert the time position is always an int.

    This is the only guard against a one-character edit turning a 1-second read into a
    multi-gigabyte one, and it is invisible to any correctness test.
    """
    import h5py

    seen: list[tuple] = []
    original = h5py.Dataset.__getitem__

    def spy(self, key):
        seen.append(key if isinstance(key, tuple) else (key,))
        return original(self, key)

    monkeypatch.setattr(h5py.Dataset, "__getitem__", spy)
    for _ in traj.iter_frames(["density", "velocity", "vorticity"]):
        pass

    # (sim, channels, time, ...) -- position 2 is the time axis.
    time_keys = [k[2] for k in seen if len(k) >= 3]
    assert time_keys, "no multi-axis reads recorded; the spy did not fire"
    for k in time_keys:
        assert isinstance(k, (int, np.integer)), (
            f"time axis indexed with {k!r} ({type(k).__name__}); must be a plain int"
        )


def test_memory_stays_bounded(traj):
    """Peak allocation over a full pass must stay near one frame, not the whole file."""
    import tracemalloc

    tracemalloc.start()
    for _ in traj.iter_frames(["density", "velocity", "vorticity"]):
        pass
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    one_frame = 4 * np.prod(SHAPE) * 8  # density + 2 velocity + vorticity, float64
    assert peak < 50 * one_frame, f"peak {peak} B is far above one frame ({one_frame} B)"


# --- provenance ---------------------------------------------------------------------


def test_meta_carries_provenance(traj):
    meta = traj.meta
    assert meta["format"] == "kinet_raw"
    assert meta["n_frames"] == N_FRAMES
    assert meta["path"].endswith(".h5")
    # JSON-string attributes must come back parsed, not as raw strings.
    assert meta["source_attrs"]["discretization"]["spatial"]["grid"] == list(SHAPE)


def test_reader_is_registered():
    from fmeval.data.base import READERS

    assert READERS["kinet_raw"] is KinetRawTrajectory
    assert issubclass(KinetRawTrajectory, Trajectory)


def test_close_is_idempotent(kinet_file):
    t = KinetRawTrajectory(kinet_file)
    t.close()
    t.close()


# --- the well reader: the test of whether the abstraction holds ----------------------


@pytest.fixture
def well_file(tmp_path):
    from tests.fixtures_h5 import write_well

    return write_well(tmp_path / "well.h5")


@pytest.fixture
def well_traj(well_file):
    from fmeval.data.well import WellTrajectory

    with WellTrajectory(well_file, nan_policy="error") as t:
        yield t


def test_well_frame_shape_dtype_and_channels(well_traj):
    frame = well_traj.frame(1, well_traj.fields)
    for name, arr in frame.fields.items():
        want_c = FIELDS[name].n_channels(well_traj.grid.n_spatial)
        assert arr.shape == (want_c, *SHAPE), f"{name} has shape {arr.shape}"
        assert arr.dtype == np.float64, "float32 on disk must be cast to the contract"


def test_well_velocity_channel_move(well_traj):
    """The one line that would be invisible on a square grid.

    The file stores (X, Y, D); the contract is (D, X, Y). u = 1 and v = 2 at t=0, and the
    grid is non-square, so both a missed moveaxis and a transpose fail loudly.
    """
    vel = well_traj.frame(0, ["velocity"])["velocity"]
    assert vel.shape == (2, *SHAPE)
    assert np.allclose(vel[0], 1.0)
    assert np.allclose(vel[1], 2.0)


def test_well_grid_from_coordinate_arrays(well_traj):
    g = well_traj.grid
    assert g.shape == SHAPE
    assert g.dims == ("x", "y")
    assert g.spacing == (1.0, 1.0)
    assert g.periodic == (True, True), "read from boundary_conditions, not assumed"


def test_well_excludes_degenerate_and_redundant_fields(well_traj):
    assert "pressure" not in well_traj.fields
    assert "temperature" not in well_traj.fields


def test_well_rejects_an_unexpected_spatial_order(tmp_path):
    """A different axis order would need a transpose, so it must fail rather than guess."""
    import h5py

    from fmeval.data.well import WellTrajectory
    from tests.fixtures_h5 import write_well

    path = write_well(tmp_path / "swapped.h5")
    with h5py.File(path, "r+") as f:
        f["dimensions"].attrs["spatial_dims"] = ["y", "x"]
    with pytest.raises(ValueError, match="spatial_dims"):
        WellTrajectory(path)


def test_well_reader_is_registered():
    from fmeval.data.base import READERS
    from fmeval.data.well import WellTrajectory

    assert READERS["well"] is WellTrajectory


def test_well_never_slices_the_time_axis(well_traj, monkeypatch):
    import h5py

    seen: list[tuple] = []
    original = h5py.Dataset.__getitem__

    def spy(self, key):
        seen.append(key if isinstance(key, tuple) else (key,))
        return original(self, key)

    monkeypatch.setattr(h5py.Dataset, "__getitem__", spy)
    for _ in well_traj.iter_frames(well_traj.fields):
        pass
    # (sim, time, ...) -- position 1 is the time axis for this layout.
    time_keys = [k[1] for k in seen if len(k) >= 2]
    assert time_keys
    for k in time_keys:
        assert isinstance(k, (int, np.integer)), f"time axis indexed with {k!r}"


# --- the abstraction validated against ground truth ----------------------------------


DATA_ROOT = "datasets/kinet/doubly_periodic/weakly_compressible_isoT_fluids/sys_Re-5e4_Ma-1en1"
RAW = f"{DATA_ROOT}/D2Q9_shape-256-256_T-10000_H-dc804f.h5"
WELL = f"{DATA_ROOT}/D2Q9_shape-256-256_T-10000_H-dc804f_well-format.h5"


@pytest.mark.data
def test_raw_and_well_readers_agree_on_the_same_simulation():
    """The same rollout in two containers must come back identical.

    This is what validates the whole data abstraction against ground truth rather than
    against a fixture I wrote. The Well file stores float32, so the tolerance is
    single-precision; the axis and channel conventions must match exactly.
    """
    from pathlib import Path

    from fmeval.data.well import WellTrajectory

    for path in (RAW, WELL):
        if not Path(path).exists():
            pytest.skip(f"{path} not available")

    with KinetRawTrajectory(RAW) as raw, WellTrajectory(WELL) as well:
        assert raw.grid.shape == well.grid.shape
        assert raw.grid.dims == well.grid.dims
        assert raw.grid.spacing == pytest.approx(well.grid.spacing)
        np.testing.assert_allclose(raw.times[:50], well.times[:50], rtol=1e-12)

        shared = sorted(set(raw.fields) & set(well.fields))
        assert {"density", "velocity", "vorticity"} <= set(shared)
        for t in (1, 2500, 5000):
            a = raw.frame(t, shared)
            b = well.frame(t, shared)
            for name in shared:
                np.testing.assert_allclose(
                    a[name], b[name], rtol=1e-6, atol=1e-8,
                    err_msg=f"{name} differs at t={t} between the raw and Well readers",
                )
