"""Ensemble metrics and the miscalibration ladder, end to end through the harness.

Three things are pinned here, in order of how quietly they would fail otherwise.

**A deterministic dataset must not produce probabilistic rows.** An ensemble metric asked
to run against a single realization has nothing to measure. It is skipped rather than
recorded as zero or NaN, because a column of zeros is indistinguishable from a metric that
found no error.

**Degrading an ensemble degrades its members.** Applying an existing per-field operator to
the reference while leaving the members untouched would make every calibration metric
measure the ladder's effect on the truth rather than on the prediction -- backwards, and
entirely plausible-looking.

**The reference is never degraded.** The ladder damages the *prediction*; the truth it is
scored against stays where it is.
"""

from __future__ import annotations

import numpy as np
import pytest

from fmeval import pipeline
from fmeval.data.synthetic_ensemble import SyntheticEnsembleTrajectory
from fmeval.ladder import build_ladder
from fmeval.pipeline import DatasetInfo
from metrics import registry

GRID = (16, 16)
N_MEMBERS = 6

ENSEMBLE_METRICS = ["crps", "spread_skill", "rank_histogram", "ensemble_mean_rmse"]


@pytest.fixture
def ensemble_traj():
    return SyntheticEnsembleTrajectory(
        grid=GRID, n_members=N_MEMBERS, n_frames=4, fields=("density",), sigma=0.2, seed=0
    )


@pytest.fixture
def info():
    return DatasetInfo(name="synthetic_ensemble_test", trajectory="test")


def _ladder(**entries):
    return build_ladder(entries, include_reference=True)


def _run(traj, metric_names, severity_levels, info, **kw):
    specs = [registry.get(n) for n in metric_names]
    return pipeline.run(
        traj, specs, severity_levels, fields=["density"], dataset=info, seed=0, **kw
    )


# --- ensemble metrics need an ensemble ----------------------------------------------


def test_ensemble_metrics_are_skipped_on_a_deterministic_dataset(info, tmp_path):
    """No rows, rather than rows full of a made-up value."""
    from fmeval.data.kinet_raw import KinetRawTrajectory
    from tests.fixtures_h5 import write_kinet_raw

    path = write_kinet_raw(tmp_path / "kinet.h5")
    with KinetRawTrajectory(path, nan_policy="error") as traj:
        result = _run(traj, ["mae", "crps"], _ladder(), info)

    rows = result.rows
    assert (rows["metric"] == "mae").any(), "the deterministic metric should still run"
    assert not (rows["metric"] == "crps").any(), "crps has no ensemble to measure"


def test_ensemble_metrics_produce_rows_on_an_ensemble_dataset(ensemble_traj, info):
    result = _run(ensemble_traj, ENSEMBLE_METRICS, _ladder(), info)
    for name in ENSEMBLE_METRICS:
        assert (result.rows["metric"] == name).any(), name


def test_n_members_is_recorded(ensemble_traj, info):
    result = _run(ensemble_traj, ["crps"], _ladder(), info)
    assert set(result.rows["n_members"].dropna().unique()) == {N_MEMBERS}


def test_n_members_is_null_for_a_deterministic_metric(ensemble_traj, info):
    """mae never sees the ensemble, so its rows must not claim an ensemble size."""
    result = _run(ensemble_traj, ["mae"], _ladder(), info)
    assert result.rows["n_members"].isna().all()


def test_target_value_is_recorded_for_a_target_valued_metric(ensemble_traj, info):
    result = _run(ensemble_traj, ["spread_skill", "crps"], _ladder(), info)
    rows = result.rows
    assert (rows.loc[rows["metric"] == "spread_skill", "target_value"] == 1.0).all()
    assert rows.loc[rows["metric"] == "crps", "target_value"].isna().all()


# --- issue 003's acceptance criterion ------------------------------------------------


def test_crps_and_spread_skill_differ_from_mae(ensemble_traj, info):
    """The acceptance criterion recorded in issues/003-ensemble-data.md.

    CRPS reduces to mean absolute error for a deterministic prediction, so on an actual
    ensemble it must not merely reproduce it -- otherwise the ensemble is contributing
    nothing and the metric is measuring the member mean by another route.
    """
    result = _run(ensemble_traj, ["mae", "crps", "spread_skill"], _ladder(), info)
    rows = result.rows
    by_metric = rows.groupby("metric", observed=True)["value"].mean()
    assert by_metric["crps"] != pytest.approx(by_metric["mae"], rel=1e-3)
    assert by_metric["spread_skill"] != pytest.approx(by_metric["mae"], rel=1e-3)


# --- the miscalibration ladder -------------------------------------------------------


def test_spread_inflate_widens_the_ensemble(ensemble_traj, info):
    """The ratio rises with the inflation factor, and is monotone in it."""
    levels = _ladder(spread_inflate={"severities": [0.0, 0.5, 1.0, 2.0]})
    result = _run(ensemble_traj, ["spread_skill"], levels, info)
    rows = result.rows[result.rows["degradation"] == "spread_inflate"]
    by_level = rows.groupby("level", observed=True)["value"].mean().sort_index()
    assert list(by_level) == sorted(by_level), list(by_level)


def test_spread_deflate_narrows_the_ensemble(ensemble_traj, info):
    levels = _ladder(spread_deflate={"severities": [0.0, 0.25, 0.5, 0.8]})
    result = _run(ensemble_traj, ["spread_skill"], levels, info)
    rows = result.rows[result.rows["degradation"] == "spread_deflate"]
    by_level = rows.groupby("level", observed=True)["value"].mean().sort_index()
    assert list(by_level) == sorted(by_level, reverse=True), list(by_level)


def test_the_reference_severity_level_is_well_calibrated(ensemble_traj, info):
    """At severity zero the synthetic ensemble is exchangeable, so the ratio is ~1."""
    levels = _ladder(spread_inflate={"severities": [0.0, 1.0]})
    result = _run(ensemble_traj, ["spread_skill"], levels, info)
    rows = result.rows
    clean = rows[rows["degradation"] == "identity"]["value"]
    assert clean.mean() == pytest.approx(1.0, abs=0.15)


def test_rank_histogram_detects_both_directions(ensemble_traj, info):
    """Under- and over-dispersion both raise the index above its calibrated floor."""
    levels = _ladder(
        spread_inflate={"severities": [2.0]}, spread_deflate={"severities": [0.8]}
    )
    result = _run(ensemble_traj, ["rank_histogram"], levels, info)
    rows = result.rows
    clean = rows[rows["degradation"] == "identity"]["value"].mean()
    inflated = rows[rows["degradation"] == "spread_inflate"]["value"].mean()
    deflated = rows[rows["degradation"] == "spread_deflate"]["value"].mean()
    assert inflated > clean
    assert deflated > clean


def test_a_broadcast_operator_degrades_the_members_not_only_the_reference(
    ensemble_traj, info
):
    """An ordinary per-field operator must reach the ensemble too.

    ``bias`` is registered against single fields and knows nothing about ensembles. If
    the ladder applied it to the reference alone, the ensemble mean would stay put and
    ``ensemble_mean_rmse`` would rise -- the same sign as the correct behaviour, which is
    why this checks the members directly rather than inferring from a metric.
    """
    levels = _ladder(bias={"severities": [0.0, 0.5]})
    frame = ensemble_traj.frame(1, ["density"])
    from fmeval.ladder import apply_severity_level

    severe = [lv for lv in levels if not lv.is_reference][-1]
    applied = apply_severity_level(severe, frame, ["density"], seed=0)

    assert applied.members is not None, "members were dropped by the ladder"
    assert not np.allclose(
        applied.members["density"], frame.members["density"]
    ), "bias never reached the ensemble members"


def test_the_reference_field_is_never_degraded(ensemble_traj, info):
    """The ladder damages the prediction; the truth on the frame stays where it is.

    ``applied.fields`` is deliberately not the reference — it is the degraded ensemble's
    mean, the prediction a deterministic metric is scored on. The reference itself lives
    on the frame, and the pipeline reads it from there; what this pins is that the
    operator never wrote back to it.
    """
    from fmeval.ladder import apply_severity_level

    levels = _ladder(spread_inflate={"severities": [2.0]})
    frame = ensemble_traj.frame(1, ["density"])
    before = frame.fields["density"].copy()
    severe = [lv for lv in levels if not lv.is_reference][-1]
    applied = apply_severity_level(severe, frame, ["density"], seed=0)

    assert np.array_equal(frame.fields["density"], before), "the truth was modified"
    assert not np.allclose(applied.members["density"], frame.members["density"])
    # Inflation preserves the mean, so the prediction handed to a pairwise metric is
    # unchanged on this axis while the ensemble behind it is not.
    assert applied.fields["density"] == pytest.approx(
        frame.members["density"].mean(axis=0), rel=1e-10
    )


def test_spread_inflate_preserves_the_ensemble_mean(ensemble_traj):
    """Inflation scales about the mean, so the ensemble's centre must not move.

    This is what makes the axis a *calibration* axis: it changes dispersion and nothing
    else, so a metric that responds to it is responding to dispersion alone.
    """
    from fmeval.ladder import apply_severity_level

    levels = _ladder(spread_inflate={"severities": [1.5]})
    frame = ensemble_traj.frame(2, ["density"])
    severe = [lv for lv in levels if not lv.is_reference][-1]
    applied = apply_severity_level(severe, frame, ["density"], seed=0)

    assert applied.members["density"].mean(axis=0) == pytest.approx(
        frame.members["density"].mean(axis=0), rel=1e-10
    )


def test_ensemble_mean_rmse_is_blind_to_the_spread_axis(ensemble_traj, info):
    """The control metric does not move when only the dispersion changes."""
    levels = _ladder(spread_inflate={"severities": [0.0, 1.0, 3.0]})
    result = _run(ensemble_traj, ["ensemble_mean_rmse"], levels, info)
    rows = result.rows[result.rows["degradation"] == "spread_inflate"]
    by_level = rows.groupby("level", observed=True)["value"].mean()
    assert by_level.std() == pytest.approx(0.0, abs=1e-9), by_level
