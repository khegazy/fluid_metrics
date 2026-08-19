"""The analysis layer: normalisation, per-axis criteria, probes, and flagging.

Built on a hand-made result frame with known answers, so failures point at the statistic
rather than at the simulation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fmeval import analysis as an
from fmeval.pipeline import RESULT_DTYPES


def make_frame(
    *,
    metric: str = "m",
    field: str = "f",
    axes: dict[str, list[float]] | None = None,
    n_frames: int = 12,
    noise: float = 0.0,
    seed: int = 0,
) -> pd.DataFrame:
    """A result frame whose values are a known function of level.

    ``axes`` maps a ladder label to the per-level values; level 0 (the reference) is added
    automatically with value 0.
    """
    axes = axes or {"a": [1.0, 2.0, 3.0, 4.0]}
    rng = np.random.default_rng(seed)
    rows = []
    for frame in range(n_frames):
        rows.append(_row(metric, field, "identity", "identity", 0, 0.0, 0.0, frame))
        for label, values in axes.items():
            family = "geometric" if "translate" in label or label == "uncorrelated" \
                else "stochastic"
            for level, value in enumerate(values, start=1):
                v = value + noise * rng.standard_normal()
                rows.append(
                    _row(metric, field, label, family, level, float(level), v, frame)
                )
    df = pd.DataFrame(rows)
    for column, dtype in RESULT_DTYPES.items():
        if column in df.columns:
            df[column] = df[column].astype(dtype)
    return df


def _row(metric, field, label, family, level, severity, value, frame):
    return {
        "dataset": "d", "dataset_family": "", "complexity_rank": 0,
        "param_reynolds": np.nan, "param_mach": np.nan, "param_resolution": 16,
        "trajectory": "t", "frame_index": frame, "time": float(frame),
        "field": field, "analysis_grid": 16, "remap_op": "block_mean",
        "metric": metric, "arity": "pairwise",
        "degradation": label, "degradation_op": label, "degradation_family": family,
        "level": level, "severity": severity, "severity_name": "s",
        "variant_label": f"{label}_l{level}" if level else "reference",
        "component": "", "value": value, "seed": 0, "wall_time_s": 1e-4,
    }


# --- normalisation --------------------------------------------------------------------


def test_uncorrelated_anchor_is_measured_when_present():
    df = make_frame(axes={"a": [1.0, 2.0], "uncorrelated": [10.0, 10.0, 10.0]})
    norm = an.normalisation(df)
    row = norm.iloc[0]
    assert row["anchor_source"] == "uncorrelated"
    assert row["value_clean"] == 0.0
    assert row["value_uncorrelated"] == pytest.approx(10.0)
    assert row["span"] == pytest.approx(10.0)
    assert not row["degenerate"]


def test_damage_is_one_at_the_anchor_and_zero_when_clean():
    df = make_frame(axes={"a": [1.0, 5.0], "uncorrelated": [10.0, 10.0]})
    scored = an.add_damage(df, an.normalisation(df))
    assert scored.loc[scored["level"] == 0, "damage"].eq(0.0).all()
    unc = scored[scored["degradation"] == "uncorrelated"]
    assert unc["damage"].median() == pytest.approx(1.0)
    a2 = scored[(scored["degradation"] == "a") & (scored["level"] == 2)]
    assert a2["damage"].median() == pytest.approx(0.5)


def test_anchor_falls_back_to_the_largest_translation_and_says_so():
    """Without a measured anchor the fallback understates it, so the source is recorded."""
    df = make_frame(axes={"translate_x": [1.0, 2.0, 6.0]})
    row = an.normalisation(df).iloc[0]
    assert row["anchor_source"] == "translate_x@max"
    assert row["value_uncorrelated"] == pytest.approx(6.0)


def test_degenerate_metric_is_marked_and_produces_no_damage():
    df = make_frame(axes={"a": [3.0, 3.0, 3.0]})
    df.loc[df["level"] == 0, "value"] = 3.0  # constant everywhere
    norm = an.normalisation(df)
    assert bool(norm.iloc[0]["degenerate"])
    assert an.add_damage(df, norm)["damage"].isna().all()


# --- per-axis criteria ------------------------------------------------------------------


def test_perfectly_monotone_axis_scores_one():
    df = make_frame(axes={"a": [1.0, 2.0, 3.0, 4.0]})
    axes = an.summarise_axes(df, n_bootstrap=0)
    row = axes[axes["degradation"] == "a"].iloc[0]
    assert row["rho"] == pytest.approx(1.0)
    assert row["monotone_fraction"] == pytest.approx(1.0)
    assert row["separability_auc_min"] == pytest.approx(1.0)


def test_non_monotone_axis_is_detected():
    df = make_frame(axes={"a": [1.0, 4.0, 2.0, 3.0]})
    row = an.summarise_axes(df, n_bootstrap=0).iloc[0]
    assert row["rho"] < 0.9
    assert row["monotone_fraction"] == pytest.approx(0.0)


def test_overlapping_severity_levels_lower_the_separability_without_hurting_rho():
    """A metric can be monotone in the median and still unable to rank two models."""
    clean = an.summarise_axes(make_frame(axes={"a": [1.0, 2.0]}, noise=0.0),
                              n_bootstrap=0).iloc[0]
    noisy = an.summarise_axes(make_frame(axes={"a": [1.0, 1.05]}, noise=0.5, seed=3),
                              n_bootstrap=0).iloc[0]
    assert clean["separability_auc_min"] == pytest.approx(1.0)
    assert noisy["separability_auc_min"] < 0.8


def test_probe_axes_get_no_rank_correlation():
    """The IN-4 field and the anchor are not severity levels; correlating them would be meaningless."""
    df = make_frame(axes={"a": [1.0, 2.0], "gaussian_impostor": [9.0],
                          "uncorrelated": [10.0, 10.0]})
    axes = an.summarise_axes(df, n_bootstrap=0)
    for label in ("gaussian_impostor", "uncorrelated"):
        row = axes[axes["degradation"] == label].iloc[0]
        assert bool(row["is_probe"])
        assert np.isnan(row["rho"])


def test_sensitivity_and_saturation_levels():
    """Span is 1.0, so the thresholds sit at 0.1 and 0.9."""
    df = make_frame(axes={"a": [0.05, 0.2, 0.95, 1.0]})
    row = an.summarise_axes(df, n_bootstrap=0).iloc[0]
    assert row["sensitivity_level"] == 2.0   # level 1 is 0.05, below 0.1; level 2 is 0.2
    assert row["saturation_level"] == 3.0    # level 3 is 0.95, the first at or above 0.9


def test_block_bootstrap_produces_a_bracketing_interval():
    df = make_frame(axes={"a": [1.0, 2.0, 3.0, 4.0]}, noise=0.4, seed=1, n_frames=40)
    row = an.summarise_axes(df, block_length=4, n_bootstrap=80, seed=0).iloc[0]
    assert np.isfinite(row["rho_ci_lo"]) and np.isfinite(row["rho_ci_hi"])
    assert row["rho_ci_lo"] <= row["rho_ci_hi"]
    assert row["rho_ci_lo"] <= row["rho"] + 1e-9


def test_bootstrap_is_skipped_when_there_are_too_few_frames():
    df = make_frame(axes={"a": [1.0, 2.0]}, n_frames=3)
    row = an.summarise_axes(df, block_length=10, n_bootstrap=50).iloc[0]
    assert np.isnan(row["rho_ci_lo"])


# --- probes ------------------------------------------------------------------------------


def test_probe_summary_reports_damage_and_the_nearest_level():
    df = make_frame(
        axes={"a": [2.0, 5.0, 8.0], "gaussian_impostor": [5.0],
              "uncorrelated": [10.0, 10.0]}
    )
    probes = an.probe_summary(df, an.normalisation(df))
    row = probes.iloc[0]
    assert row["gaussian_impostor_damage"] == pytest.approx(0.5)
    assert row["gaussian_impostor_nearest_level"] == "a=2"
    assert row["uncorrelated_damage"] == pytest.approx(1.0)


# --- roll-up and flagging ------------------------------------------------------------------


def _card(axes_values, thresholds=None):
    df = make_frame(axes=axes_values)
    norm = an.normalisation(df)
    axes = an.summarise_axes(df, n_bootstrap=0)
    probes = an.probe_summary(df, norm)
    card = an.report_card(axes, probes, norm)
    return an.flag(card, thresholds or {"spearman": 0.9, "separability_auc": 0.8,
                                        "impostor_damage": 0.5})


def test_report_card_reports_the_worst_axis():
    card = _card({"good": [1.0, 2.0, 3.0], "bad": [1.0, 3.0, 2.0],
                  "uncorrelated": [10.0, 10.0]})
    row = card.iloc[0]
    assert row["worst_axis"] == "bad"
    assert row["rho_min"] < row["rho_median"]
    assert row["n_axes"] == 2


def test_report_card_has_no_verdict_column():
    """The suite reports measurements; the panel decision is made by people."""
    card = _card({"a": [1.0, 2.0], "uncorrelated": [10.0, 10.0]})
    assert "verdict" not in card.columns
    assert "accept" not in " ".join(card.columns)


def test_flags_name_the_thresholds_that_were_not_met():
    card = _card({"a": [1.0, 3.0, 2.0], "uncorrelated": [10.0, 10.0]})
    flags = card.iloc[0]["flags"]
    assert "spearman=" in flags


def test_empty_flags_when_everything_clears_the_thresholds():
    card = _card({"a": [1.0, 2.0, 3.0], "gaussian_impostor": [9.0],
                  "uncorrelated": [10.0, 10.0]})
    assert card.iloc[0]["flags"] == ""


def test_flagging_is_separate_from_computation():
    """Re-flagging with different thresholds must need no recomputation."""
    df = make_frame(axes={"a": [1.0, 2.0, 3.0], "uncorrelated": [10.0, 10.0]})
    norm = an.normalisation(df)
    card = an.report_card(an.summarise_axes(df, n_bootstrap=0),
                          an.probe_summary(df, norm), norm)
    strict = an.flag(card, {"spearman": 1.5})
    loose = an.flag(card, {"spearman": 0.1})
    assert strict.iloc[0]["flags"] != ""
    assert loose.iloc[0]["flags"] == ""
    assert "flags" not in card.columns, "flag() must not mutate its input"


# --- cross-metric --------------------------------------------------------------------------


def test_cross_metric_correlation_finds_duplicates():
    a = make_frame(metric="a", axes={"x": [1.0, 2.0, 3.0, 4.0]})
    b = make_frame(metric="b", axes={"x": [2.0, 4.0, 6.0, 8.0]})   # perfectly redundant
    c = make_frame(metric="c", axes={"x": [4.0, 3.0, 2.0, 1.0]})   # anti-correlated
    rho = an.cross_metric_correlation(pd.concat([a, b, c], ignore_index=True))
    assert rho.loc["a", "b"] == pytest.approx(1.0)
    assert rho.loc["a", "c"] == pytest.approx(-1.0)


def test_cross_metric_correlation_excludes_the_reference_level():
    """Every pairwise metric is 0 there, so keeping it would pull correlations to +1."""
    a = make_frame(metric="a", axes={"x": [1.0, 2.0, 3.0, 4.0]})
    c = make_frame(metric="c", axes={"x": [4.0, 3.0, 2.0, 1.0]})
    rho = an.cross_metric_correlation(pd.concat([a, c], ignore_index=True))
    assert rho.loc["a", "c"] == pytest.approx(-1.0)


def test_cross_metric_correlation_needs_two_metrics():
    assert an.cross_metric_correlation(make_frame()).empty


def test_selectivity_profile_is_one_row_per_metric():
    df = pd.concat(
        [make_frame(metric=m, axes={"x": [1.0, 2.0], "y": [1.0, 3.0],
                                    "uncorrelated": [9.0, 9.0]})
         for m in ("a", "b")],
        ignore_index=True,
    )
    profile = an.selectivity_profile(an.summarise_axes(df, n_bootstrap=0))
    assert set(profile["metric"]) == {"a", "b"}
    assert {"x", "y"} <= set(profile.columns)
    assert "uncorrelated" not in profile.columns, "probes are not axes"


# --- pooled vs per-frame correlation ---------------------------------------------------------


def test_per_frame_correlation_survives_a_trend_in_the_field():
    """The defect this statistic exists to avoid.

    A field whose amplitude grows along the trajectory makes the pooled correlation
    meaningless: the worst severity level early is smaller than the mildest severity level late. Measured on
    the real density field, every axis was perfectly ordered within every frame while the
    pooled value read between 0.10 and 0.91.
    """
    rows = []
    for frame in range(10):
        scale = 10.0 ** frame          # six orders of magnitude across the trajectory
        rows.append(_row("m", "f", "identity", "identity", 0, 0.0, 0.0, frame))
        for level, step in enumerate([1.0, 2.0, 3.0, 4.0], start=1):
            rows.append(_row("m", "f", "a", "stochastic", level, float(level),
                             step * scale, frame))
    df = pd.DataFrame(rows)
    for column, dtype in RESULT_DTYPES.items():
        if column in df.columns:
            df[column] = df[column].astype(dtype)

    row = an.summarise_axes(df, n_bootstrap=0).iloc[0]
    assert row["rho"] == pytest.approx(1.0), "per-frame correlation must be unaffected"
    assert row["monotone_fraction"] == pytest.approx(1.0)
    assert row["rho_pooled"] < 0.8, (
        "the pooled value should be visibly degraded here; if it is not, this test no "
        "longer demonstrates the difference"
    )


def test_per_frame_correlation_still_detects_a_genuinely_bad_axis():
    """Robustness to a trend must not come at the cost of sensitivity."""
    df = make_frame(axes={"a": [4.0, 3.0, 2.0, 1.0]})   # exactly inverted
    row = an.summarise_axes(df, n_bootstrap=0).iloc[0]
    assert row["rho"] == pytest.approx(-1.0)
    assert row["monotone_fraction"] == pytest.approx(0.0)
