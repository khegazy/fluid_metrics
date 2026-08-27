"""What a deterministic metric measures on an ensemble dataset.

A pairwise metric asked to run against an ensemble has a genuine ambiguity: the ladder
damages the *members*, so the reference field beside them is undamaged, and comparing the
reference with itself returns exactly zero at every severity. A column of zeros is the
worst possible outcome -- it is indistinguishable from a metric that ran and found no
error, and it would sit in the report beside the probabilistic metrics looking like a
result.

The ensemble's point prediction is its mean, so that is what a pairwise metric is given.
It then measures what it has always measured, on the prediction rather than on the truth,
and `mae` on an ensemble run means the same thing as `mae` on a deterministic one.
"""

from __future__ import annotations

import numpy as np
import pytest

from fmeval import pipeline
from fmeval.data.synthetic_ensemble import SyntheticEnsembleTrajectory
from fmeval.ladder import build_ladder
from fmeval.pipeline import DatasetInfo
from metrics import registry


@pytest.fixture
def traj():
    return SyntheticEnsembleTrajectory(
        grid=(16, 16), n_members=8, n_frames=3, fields=("density",), sigma=0.2, seed=0
    )


def _run(traj, names, levels):
    specs = [registry.get(n) for n in names]
    return pipeline.run(
        traj, specs, levels, fields=["density"],
        dataset=DatasetInfo(name="synthetic_ensemble_test"), seed=0,
    )


def test_a_pairwise_metric_does_not_report_all_zeros(traj):
    """The failure this exists to prevent: a column that looks like a perfect score."""
    levels = build_ladder({"bias": {"severities": [0.0, 0.5]}}, include_reference=True)
    rows = _run(traj, ["mae"], levels).rows
    values = rows["value"].to_numpy()
    assert not np.allclose(values, 0.0), (
        "mae returned zero everywhere: it was handed the reference twice, so it compared "
        "the truth with itself rather than measuring the prediction"
    )


def test_a_pairwise_metric_scores_the_ensemble_mean(traj):
    """Explicitly: the candidate is the member mean, the ensemble's point prediction."""
    from metrics.mae.metric import mae

    levels = build_ladder({}, include_reference=True)
    rows = _run(traj, ["mae"], levels).rows

    frame = traj.frame(0, ["density"])
    want = mae(frame.fields["density"], frame.members["density"].mean(axis=0))
    got = rows[rows["frame_index"] == 0]["value"].iloc[0]
    assert got == pytest.approx(want, rel=1e-12)


def test_it_agrees_with_the_ensemble_mean_metric(traj):
    """`mae` and `ensemble_mean_rmse` now measure the same prediction, differing only in norm."""
    levels = build_ladder({}, include_reference=True)
    rows = _run(traj, ["mae", "ensemble_mean_rmse"], levels).rows
    by_metric = rows.groupby("metric", observed=True)["value"].mean()
    # Both are errors of the same field against the same reference, so the L1 mean is
    # bounded above by the L2 root-mean-square. A gross disagreement means they are not
    # looking at the same pair of arrays.
    assert 0 < by_metric["mae"] <= by_metric["ensemble_mean_rmse"]


def test_a_pairwise_metric_responds_to_the_bias_axis(traj):
    """Biasing the members moves their mean, so a pairwise metric must see it."""
    levels = build_ladder(
        {"bias": {"severities": [0.0, 0.2, 0.5, 1.0]}}, include_reference=True
    )
    rows = _run(traj, ["mae"], levels).rows
    axis = rows[rows["degradation"] == "bias"]
    by_level = axis.groupby("level", observed=True)["value"].mean().sort_index()
    assert list(by_level) == sorted(by_level), list(by_level)


def test_a_pairwise_metric_is_flat_on_a_dispersion_axis(traj):
    """Scaling the members about their mean leaves that mean, so a pairwise metric is blind.

    Correct, and worth pinning: it is the same blindness `ensemble_mean_rmse` has, and it
    is why a dispersion failure needs a probabilistic metric to detect at all.
    """
    levels = build_ladder(
        {"spread_inflate": {"severities": [0.0, 1.0, 3.0]}}, include_reference=True
    )
    rows = _run(traj, ["mae"], levels).rows
    axis = rows[rows["degradation"] == "spread_inflate"]
    by_level = axis.groupby("level", observed=True)["value"].mean()
    assert by_level.std() == pytest.approx(0.0, abs=1e-12)


def test_a_single_field_metric_characterises_the_prediction():
    """An arity="single" metric also describes the prediction, not the reference.

    Uses velocity, since the single-field metrics in this repository are declared against
    velocity or vorticity rather than against any field.
    """
    traj = SyntheticEnsembleTrajectory(
        grid=(16, 16), n_members=8, n_frames=3, fields=("velocity",), sigma=0.2, seed=0
    )
    levels = build_ladder({"bias": {"severities": [0.0, 1.0]}}, include_reference=True)
    specs = [registry.get("kinetic_energy")]
    rows = pipeline.run(
        traj, specs, levels, fields=["velocity"],
        dataset=DatasetInfo(name="synthetic_ensemble_test"), seed=0,
    ).rows

    axis = rows[rows["degradation"] == "bias"]
    assert not axis.empty, "no rows: the metric never ran on this field"
    assert axis["value"].nunique() > 1, (
        "a single-field metric returned the same value at every severity: it is "
        "characterising the undamaged reference rather than the prediction"
    )
