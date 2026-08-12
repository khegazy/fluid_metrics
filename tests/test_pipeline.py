"""The evaluation loop and the run-folder layout.

The schema test is the load-bearing one: every plot, table and analysis downstream is a
groupby on that frame, so its columns and dtypes are frozen deliberately.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from fmeval import io as fio
from fmeval.data.base import TimeSelection
from fmeval.data.kinet_raw import KinetRawTrajectory
from fmeval.ladder import build_ladder
from fmeval.pipeline import RESULT_DTYPES, DatasetInfo, MapRequest, empty_results, run
from metrics import registry as metric_registry
from tests.fixtures_h5 import SHAPE, write_kinet_raw

LADDER = {
    "gaussian_blur": {"severities": [1.0, 2.0]},
    "translate_x": {"op": "translate", "severities": [1, 2], "options": {"axis": "x"}},
    "gaussian_impostor": {"severities": [0]},
}
INFO = DatasetInfo(
    name="synthetic",
    trajectory="fixture",
    family="test_family",
    rank=0,
    params={"reynolds": 5.0e4, "mach": 0.1, "resolution": SHAPE[0]},
)


@pytest.fixture
def traj(tmp_path):
    with KinetRawTrajectory(write_kinet_raw(tmp_path / "d.h5")) as t:
        yield t


def evaluate(traj, metric_names=("mse", "mae"), **kw):
    specs = [metric_registry.get(n) for n in metric_names]
    rungs = build_ladder(LADDER)
    kw.setdefault("selection", TimeSelection(start=1))
    return run(traj, specs, rungs, fields=["density", "velocity"],
               dataset=INFO, seed=7, **kw)


# --- schema -------------------------------------------------------------------------


def test_result_schema_is_exact(traj):
    """Frozen: columns, order and dtypes. Everything downstream depends on it."""
    df = evaluate(traj).rows
    assert list(df.columns) == list(RESULT_DTYPES)
    for column, dtype in RESULT_DTYPES.items():
        actual = df[column].dtype
        if dtype == "category":
            # pandas_dtype("category") carries no categories, so compare the kind.
            assert isinstance(actual, pd.CategoricalDtype), column
        else:
            assert actual == pd.api.types.pandas_dtype(dtype), column


def test_empty_results_matches_the_schema():
    df = empty_results()
    assert list(df.columns) == list(RESULT_DTYPES)
    assert len(df) == 0


def test_row_count(traj):
    """n_frames x n_metrics x n_fields x n_variants for pairwise metrics."""
    result = evaluate(traj)
    n_frames = 4               # start=1 over a 5-frame fixture
    n_variants = 1 + 2 + 2 + 1  # reference + blur + translate + impostor
    assert len(result.rows) == n_frames * 2 * 2 * n_variants
    assert result.n_frames == n_frames


def test_provenance_is_on_every_row(traj):
    df = evaluate(traj).rows
    assert set(df["dataset"]) == {"synthetic"}
    assert set(df["dataset_family"]) == {"test_family"}
    assert set(df["complexity_rank"]) == {0}
    assert set(df["param_reynolds"]) == {5.0e4}
    assert set(df["seed"]) == {7}


# --- correctness of the loop ----------------------------------------------------------


def test_reference_rung_is_exactly_zero_for_pairwise_metrics(traj):
    df = evaluate(traj).rows
    ref = df[df["variant_label"] == "reference"]
    assert len(ref) > 0
    assert (ref["value"] == 0.0).all()


def test_every_axis_is_present_for_every_frame_and_field(traj):
    df = evaluate(traj).rows
    counts = df.groupby(["metric", "field", "frame_index"], observed=True)[
        "variant_label"
    ].nunique()
    assert set(counts) == {6}


def test_single_field_metric_is_evaluated_on_the_reference_too(traj):
    """Single-field metrics measure the field, so the reference gets a real value."""
    result = evaluate(traj, metric_names=("kinetic_energy",))
    df = result.rows
    assert set(df["field"]) == {"velocity"}, "should skip fields it does not accept"
    ref = df[df["variant_label"] == "reference"]
    assert (ref["value"] > 0).all(), "kinetic energy of the reference is not zero"


def test_metric_that_accepts_no_available_field_yields_nothing(traj):
    result = run(
        traj, [metric_registry.get("enstrophy")], build_ladder(LADDER),
        fields=["density"], dataset=INFO, seed=0, selection=TimeSelection(start=1),
    )
    assert len(result.rows) == 0


def test_wall_time_is_recorded_and_positive(traj):
    df = evaluate(traj).rows
    assert (df["wall_time_s"] > 0).all()


def test_results_are_reproducible(traj):
    a = evaluate(traj).rows
    b = evaluate(traj).rows
    pd.testing.assert_series_equal(a["value"], b["value"])


def test_reduction_does_not_change_per_frame_values(traj):
    """Seeding from content, not call order: a frame's numbers must not depend on
    which other frames were selected.

    The guarantee is exact on an uncalibrated axis and only approximate on a calibrated one.
    A calibrated severity is resolved against a spectrum measured from the frames actually
    evaluated, so striding the selection samples a slightly different set of frames and moves
    the resolved cutoffs and widths a little. Measured here, that is a relative shift of about
    5e-6 -- far above float noise and far below anything a metric comparison would notice. It
    is a real cost of calibration, and it is consistent with the existing rule that two runs at
    different reductions are not directly comparable; if it ever needs to be exact, the
    calibration has to be pinned in config rather than measured.
    """
    full = evaluate(traj, selection=TimeSelection(start=1)).rows
    strided = evaluate(traj, selection=TimeSelection(start=1, reduction=2)).rows
    key = ["metric", "field", "variant_label", "frame_index"]
    merged = full.merge(strided, on=key, suffixes=("_full", "_red"))
    assert len(merged) > 0

    calibrated = merged["calibration_full"].astype(str).ne("")
    np.testing.assert_allclose(
        merged.loc[~calibrated, "value_full"], merged.loc[~calibrated, "value_red"],
        rtol=1e-12, err_msg="an uncalibrated axis must be bitwise reproducible",
    )
    assert calibrated.any(), "no calibrated axis in the fixture ladder; this test is vacuous"
    np.testing.assert_allclose(
        merged.loc[calibrated, "value_full"], merged.loc[calibrated, "value_red"],
        rtol=1e-3, err_msg="calibration drift between reductions is larger than expected",
    )


def test_empty_selection_raises(traj):
    with pytest.raises(ValueError, match="time selection is empty"):
        evaluate(traj, selection=TimeSelection(start=99))


# --- analysis grid --------------------------------------------------------------------


def test_analysis_grid_is_recorded_and_applied(traj):
    result = evaluate(traj, analysis_resolution=SHAPE[0] // 2)
    df = result.rows
    assert set(df["analysis_grid"]) == {SHAPE[0] // 2}
    assert set(df["remap_op"]) == {"block_mean"}


def test_coarser_analysis_grid_changes_the_numbers(traj):
    native = evaluate(traj).rows
    coarse = evaluate(traj, analysis_resolution=SHAPE[0] // 2).rows
    key = ["metric", "field", "variant_label", "frame_index"]
    merged = native.merge(coarse, on=key, suffixes=("_n", "_c"))
    blurred = merged[merged["variant_label"] == "gaussian_blur_l2"]
    assert not np.allclose(blurred["value_n"], blurred["value_c"])


# --- pointwise maps ---------------------------------------------------------------------


def test_maps_are_stored_only_for_the_requested_combinations(traj):
    result = evaluate(
        traj,
        maps=MapRequest(enabled=True, frames=[-1], axes=["gaussian_blur"],
                        fields=["density"]),
    )
    assert result.maps, "no maps stored"
    for key, arr in result.maps.items():
        assert "gaussian_blur" in key
        assert ":density__" in key
        assert arr.shape == SHAPE, "map must have the channel axis reduced away"


def test_maps_are_disabled_by_default(traj):
    assert evaluate(traj).maps == {}


# --- run folders ------------------------------------------------------------------------


def test_run_folder_round_trip(tmp_path, traj):
    result = evaluate(traj, maps=MapRequest(enabled=True, frames=[-1]))
    folder = fio.make_run_folder(tmp_path, "mse", 1234567890)
    assert folder.root.name == "mse_1234567890"

    fio.write_results(folder, result.rows)
    digest = fio.write_config(folder, {"metrics": ["mse"], "seed": 7}, ["metrics=[mse]"])
    fio.write_maps(folder, result.maps)
    fio.write_run_meta(folder, run_id=1234567890, config_hash=digest)

    reloaded = fio.read_results(folder)
    assert len(reloaded) == len(result.rows)
    assert list(reloaded.columns) == list(RESULT_DTYPES)

    meta = json.loads((folder.data / "run_meta.json").read_text())
    assert meta["config_hash"] == digest
    assert "mse" in meta["registries"]["metrics"]
    assert "gaussian_impostor" in meta["registries"]["degradations"]
    assert meta["registries"]["degradations"]["gaussian_impostor"]["ordinal"] is False


def test_config_hash_is_stable_and_sensitive(tmp_path):
    a = fio.make_run_folder(tmp_path / "a", "m", 1)
    b = fio.make_run_folder(tmp_path / "b", "m", 1)
    c = fio.make_run_folder(tmp_path / "c", "m", 1)
    h1 = fio.write_config(a, {"seed": 1, "metrics": ["mse"]})
    h2 = fio.write_config(b, {"metrics": ["mse"], "seed": 1})  # same content, other order
    h3 = fio.write_config(c, {"seed": 2, "metrics": ["mse"]})
    assert h1 == h2, "the hash must not depend on key order"
    assert h1 != h3, "the hash must change when a setting changes"


def test_load_runs_concatenates_and_tags(tmp_path, traj):
    rows = evaluate(traj).rows
    for name in ("mse", "mae"):
        folder = fio.make_run_folder(tmp_path, name, 42)
        fio.write_results(folder, rows[rows["metric"] == name])
    combined = fio.load_runs("*_42", root=tmp_path)
    assert set(combined["run_dir"]) == {"mse_42", "mae_42"}
    assert len(combined) == len(rows)


def test_load_runs_without_matches_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="no run folders"):
        fio.load_runs("nothing_*", root=tmp_path)
