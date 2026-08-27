"""Ordering statistics for a metric whose best value is not zero.

Every one-sided statistic in :mod:`fmeval.analysis` -- monotonicity, the adjacent-severity
AUC, the sensitivity and saturation thresholds, the rank correlation -- assumes damage
moves the value in one direction. That assumption fails for the spread-to-skill ratio,
which is calibrated at one and wrong on both sides of it: an ensemble that hedges reads
high, one that is overconfident reads low, and both are worse than the middle.

The repository adapts rather than the metric. ``spread_skill`` reports the raw ratio, as
the forecasting literature does, and declares ``target=1.0``; the analysis orders by
distance from that target. What is *reported* stays the ratio -- a reader still sees 0.4
and knows the ensemble is too narrow -- while what is *ranked* is how far from calibrated
it is.

Without this, a perfectly behaved calibration axis arrives in the report card flagged on
three criteria at once, and the flag says the metric is broken when the analysis is.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fmeval.analysis import summarise_axes


def _frame(values_by_level: dict[int, list[float]], *, metric: str,
           target: float | None, n_frames: int = 6) -> pd.DataFrame:
    """A tidy result frame for one axis, with a value per level per frame.

    Built by filling the real :data:`fmeval.pipeline.RESULT_DTYPES` schema rather than a
    hand-listed subset, so a new required column cannot make this fixture quietly
    diverge from what the pipeline actually emits.
    """
    from fmeval.pipeline import RESULT_DTYPES

    defaults: dict[str, object] = {
        "dataset": "d",
        "dataset_family": "",
        "complexity_rank": 0,
        "param_reynolds": np.nan,
        "param_mach": np.nan,
        "param_resolution": 64,
        "trajectory": "t",
        "time": 0.0,
        "field": "density",
        "analysis_grid": 64,
        "remap_op": "block_mean",
        "metric": metric,
        "arity": "ensemble",
        "higher_is_better": False,
        "degradation_op": "spread_inflate",
        "degradation_family": "ensemble",
        "severity": 0.0,
        "severity_nominal": 0.0,
        "calibration": "",
        "severity_degenerate": False,
        "energy_removed": 0.0,
        "energy_changed": 0.0,
        "severity_name": "excess dispersion",
        "variant_label": "spread_inflate",
        "component": "",
        "seed": 0,
        "wall_time_s": 0.0,
        "n_members": 8,
        "target_value": np.nan if target is None else target,
    }

    rows = []
    for level, values in values_by_level.items():
        for frame_index in range(n_frames):
            row = dict(defaults)
            row.update(
                degradation="identity" if level == 0 else "spread_inflate",
                level=level,
                frame_index=frame_index,
                value=values[frame_index % len(values)],
                severity=float(level),
                severity_nominal=float(level),
            )
            rows.append({key: row[key] for key in RESULT_DTYPES})
    return pd.DataFrame(rows)


def _row(df: pd.DataFrame, axis: str = "spread_inflate") -> pd.Series:
    out = summarise_axes(df)
    return out[out["degradation"] == axis].iloc[0]


def test_a_ratio_falling_away_from_its_target_is_ranked_as_worsening():
    """Overconfidence: the ratio falls from 1.0 toward 0.2 as damage rises.

    Ranked by raw value this is a perfectly *decreasing* axis and would score rho = -1
    against a statistic expecting a rise. Ranked by distance from the target it is what
    it actually is: monotonically worsening.
    """
    df = _frame(
        {0: [1.0], 1: [0.8], 2: [0.55], 3: [0.35], 4: [0.2]},
        metric="spread_skill",
        target=1.0,
    )
    row = _row(df)
    assert row["rho"] == pytest.approx(1.0)
    assert row["monotone_fraction"] == pytest.approx(1.0)


def test_a_ratio_rising_away_from_its_target_is_also_ranked_as_worsening():
    """Hedging: the same axis in the other direction must score the same way.

    This is the half a sign convention cannot express. Whatever single direction were
    declared, one of these two tests would fail.
    """
    df = _frame(
        {0: [1.0], 1: [1.4], 2: [2.0], 3: [3.1], 4: [4.5]},
        metric="spread_skill",
        target=1.0,
    )
    row = _row(df)
    assert row["rho"] == pytest.approx(1.0)
    assert row["monotone_fraction"] == pytest.approx(1.0)


def test_the_reported_value_is_still_the_raw_ratio():
    """The orientation is internal to the ranking; the number a reader sees is unchanged."""
    df = _frame(
        {0: [1.0], 1: [0.8], 2: [0.55], 3: [0.35], 4: [0.2]},
        metric="spread_skill",
        target=1.0,
    )
    out = summarise_axes(df)
    row = out[out["degradation"] == "spread_inflate"].iloc[0]
    # Whatever summary columns carry the metric's own value, none of them may have been
    # replaced by a distance: the clean value is the ratio 1.0, not 0.0.
    assert row["value_clean"] == pytest.approx(1.0)


def test_a_metric_without_a_target_is_untouched():
    """The ordinary error case must behave exactly as it did before targets existed."""
    df = _frame(
        {0: [0.0], 1: [0.2], 2: [0.5], 3: [0.9], 4: [1.6]},
        metric="crps",
        target=None,
    )
    row = _row(df)
    assert row["rho"] == pytest.approx(1.0)
    assert row["monotone_fraction"] == pytest.approx(1.0)


def test_a_non_monotone_excursion_is_still_caught():
    """The transform must not launder a genuinely disordered axis into a clean one.

    Here the ratio jumps past the target and back, so its distance from the target is not
    monotone either, and the statistics must say so.
    """
    df = _frame(
        {0: [1.0], 1: [0.5], 2: [1.05], 3: [0.4], 4: [1.0]},
        metric="spread_skill",
        target=1.0,
    )
    row = _row(df)
    assert row["rho"] < 0.9
    assert row["monotone_fraction"] < 1.0


def test_a_value_at_or_below_zero_does_not_break_the_ranking():
    """A collapsed ensemble reads exactly zero, which a log-ratio cannot take.

    Zero is a real, reachable value of this metric -- the ensemble has no spread at all --
    so it must be ranked as the worst point on the axis rather than dropped or turned
    into a NaN that silently shrinks the sample.
    """
    df = _frame(
        {0: [1.0], 1: [0.6], 2: [0.3], 3: [0.1], 4: [0.0]},
        metric="spread_skill",
        target=1.0,
    )
    row = _row(df)
    assert np.isfinite(row["rho"])
    assert row["rho"] == pytest.approx(1.0)
