"""Turn the tidy result frame into the reported criteria.

This module computes numbers only. The separate :func:`flag` pass compares them against
configured reference thresholds, so the two can never be confused and re-flagging with
different thresholds needs no recomputation. **Nothing here labels a metric accepted or
rejected** -- the flags exist to draw attention to a row, and the panel decision is the
team's.

Two rules that keep the numbers honest:

**Rank correlation is computed within one ladder axis, never across.** ``gaussian_blur
sigma=2`` and ``translate_x=4`` have no order relative to each other, and neither do
``gaussian_blur`` and ``median_blur`` even though both belong to the ``smoothing``
family. The unit is the ladder entry. Where one number per metric is wanted, the minimum
across axes is reported -- the honest worst case.

**The IN-4 field is excluded from every rank correlation**, by its ``ordinal=False``
declaration. It is a separate probe, not a severity level.
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Mapping
from itertools import pairwise

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr

log = logging.getLogger(__name__)

#: Ladder labels that are probes or reference measurements, not monotone axes.
PROBE_LABELS: frozenset[str] = frozenset({"gaussian_impostor", "uncorrelated"})

#: Label of the measured anchor: the value a metric gives two statistically identical but
#: positionally unrelated fields. Defines D = 1.
UNCORRELATED_LABEL: str = "uncorrelated"

#: Fraction of the clean-to-uncorrelated range at which a metric counts as having
#: departed from clean. Fixed once here and never tuned per metric.
SENSITIVITY_FRACTION: float = 0.10

#: Fraction of the uncorrelated limit at which a metric counts as saturated.
SATURATION_FRACTION: float = 0.90

#: Relative size below which a quantity counts as round-off rather than signal, measured
#: against the largest value in the same group.
#:
#: Two things use it. The damage score needs its ``clean``-to-``uncorrelated`` span to be a
#: real span, and a metric invariant to the operator the anchor is built from has no span at
#: all -- most of the position-tolerant family this project exists to develop is invariant to
#: translation, which is how the anchor is constructed. The rank correlation needs the values
#: it is ranking to differ by more than the last few bits, and ``np.roll`` changes the
#: summation order inside ``np.mean`` even when it cannot change the quantity, which was
#: enough to produce a reported ``rho`` of 0.707 on an axis whose values spanned a relative
#: 1.6e-16. Both are round-off presented as measurement.
#:
#: 1e-9 rather than something nearer the float64 epsilon: accumulated round-off over a 256^2
#: reduction is several orders of magnitude above 2.2e-16, while the mildest severity level that
#: does real work on this data moves the value by 1e-4 of its range. Nothing measured falls in the
#: gap between.
DEGENERATE_SPAN: float = 1e-9


# --- normalisation --------------------------------------------------------------------


def normalisation(df: pd.DataFrame,
                  *, uncorrelated_label: str = UNCORRELATED_LABEL) -> pd.DataFrame:
    """Anchors that put every metric on one dimensionless scale.

    Raw mean squared error and a raw transport distance are not comparable, so a *damage
    score* is defined per (dataset, metric, field):

        D = (v - clean) / (uncorrelated - clean)

    ``clean`` is the median value on the reference severity level. ``uncorrelated`` is *measured*,
    not inferred: the ``uncorrelated`` ladder entry applies several large random
    translations, which preserve every statistic exactly while destroying alignment, and
    the metric is evaluated against those. D = 1 then means "as different as two unrelated
    fields", which is what makes the score readable across metrics with different units.

    Scavenging the largest configured translation severity level instead would understate the anchor
    badly: on the real data a 16-cell displacement only reaches about 0.6 of the true
    uncorrelated value, so every damage score would be inflated by roughly 1.6x.

    A ratio to the clean value is not usable here: mean squared error on the reference severity
    level is exactly zero. Per-figure min-max scaling is not usable either, because the figure would
    change whenever a severity level is added.

    Returns:
        One row per (dataset, metric, field) with ``value_clean``, ``value_uncorrelated``,
        ``span``, ``anchor_source`` and ``degenerate``.
    """
    rows = []
    for (dataset, metric, field), g in df.groupby(
        ["dataset", "metric", "field"], observed=True
    ):
        clean = float(g.loc[g["level"] == 0, "value"].median()) if (g["level"] == 0).any() \
            else float("nan")
        high, source = _uncorrelated_anchor(g, uncorrelated_label)
        span = high - clean
        # The scale is the LARGEST value anywhere in the group, not the median. The median is
        # defeated in exactly the case this guard exists for: a metric invariant to the
        # operator the anchor is built from returns round-off on the anchor, on the impostor
        # and on every translation severity level, so more than half the rows are round-off and the
        # median collapses to round-off with them -- the guard then compares noise against
        # noise and passes. Measured with a spectral metric of the BD-1 shape on the real
        # trajectory: the anchor was 1.5e-16 against a genuine blur response of 3.5e-1, and
        # the impostor was reported at damage 1.17, which reads as "worse than two unrelated
        # fields" for a metric that cannot separate any of them.
        scale = float(np.nanmax(np.abs(g["value"].to_numpy()))) or 1.0
        rows.append(
            {
                "dataset": dataset,
                "metric": metric,
                "field": field,
                "value_clean": clean,
                "value_uncorrelated": high,
                "span": span,
                "anchor_source": source,
                "degenerate": not np.isfinite(span) or abs(span) < DEGENERATE_SPAN * scale,
            }
        )
    return pd.DataFrame(rows)


def _uncorrelated_anchor(g: pd.DataFrame, preferred: str) -> tuple[float, str]:
    """Estimate the value two statistically identical but unaligned fields would give."""
    if preferred and (g["degradation"] == preferred).any():
        sub = g[g["degradation"] == preferred]
        return float(sub["value"].median()), preferred

    # Fall back to the largest configured translation. This UNDERSTATES the anchor --
    # 16 cells reaches only ~0.6 of the true value on this data -- so the source is
    # recorded and the report says so.
    for label in ("translate_x", "translate_subpixel", "translate_y"):
        sub = g[g["degradation"] == label]
        if not sub.empty:
            top = sub.loc[sub["level"] == sub["level"].max()]
            return float(top["value"].median()), f"{label}@max"

    # Otherwise fall back to the worst severity level of any ordinal axis, and say so.
    ordinal = g[~g["degradation"].isin(PROBE_LABELS)]
    if ordinal.empty:
        return float("nan"), "none"
    worst = ordinal.loc[ordinal["value"].abs().idxmax()]
    return float(worst["value"]), f"{worst['degradation']}@max"


def add_damage(df: pd.DataFrame, norm: pd.DataFrame) -> pd.DataFrame:
    """Attach the dimensionless damage score ``D`` to every row."""
    keys = ["dataset", "metric", "field"]
    out = df.merge(norm[[*keys, "value_clean", "span", "degenerate"]], on=keys, how="left")
    with np.errstate(invalid="ignore", divide="ignore"):
        out["damage"] = (out["value"] - out["value_clean"]) / out["span"]
    out.loc[out["degenerate"], "damage"] = np.nan
    return out.drop(columns=["value_clean", "span", "degenerate"])


def _declared_target(g: pd.DataFrame) -> float | None:
    """The value a calibrated prediction attains, when the metric declares one.

    ``None`` for the ordinary case, where the metric is an error and zero is best.
    """
    if "target_value" not in g.columns:
        return None
    values = g["target_value"].dropna().unique()
    if len(values) == 0:
        return None
    target = float(values[0])
    return target if np.isfinite(target) and target > 0 else None


def _target_distance(values: pd.Series, target: float) -> pd.Series:
    """How far each value sits from ``target``, on a scale where the ratio is symmetric.

    A ratio lives on a multiplicative scale: half the calibrated spread and twice it are
    equally wrong, and a difference from the target would call the second one four times
    worse than the first. The log ratio makes them equal, which is the whole reason the
    spread-to-skill literature reads this quantity multiplicatively.

    Zero and negative values are real and reachable -- an ensemble collapsed onto its
    mean has exactly no spread -- and a log cannot take them. They are the furthest thing
    from calibrated there is, so they map to positive infinity rather than to NaN: a NaN
    would drop the severity level from the rank correlation and quietly shrink the axis
    it is meant to be the worst point of.
    """
    v = values.to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.abs(np.log(v / target))
    return pd.Series(np.where(v > 0, out, np.inf), index=values.index)


def response_direction(df: pd.DataFrame,
                       norm: pd.DataFrame | None = None) -> dict[tuple, int]:
    """Which way each metric's value moves as damage rises: ``+1`` up, ``-1`` down.

    Three of the ordering statistics below are one-sided -- monotonicity requires a rising
    difference, the Mann-Whitney AUC is taken with ``alternative="greater"``, and the
    threshold levels look for the first median to exceed a target. Applied blind they assume
    every metric is an error measure. A metric where larger means a better match then arrives
    in the report card flagged on three criteria at once while being perfectly well behaved:
    measured on an axis falling cleanly from 1.0 to 0.2, ``rho = -1.0``,
    ``monotone_fraction = 0.0`` and ``separability_auc_min = 0.0``. That shape is not
    hypothetical -- it is any correlation, SSIM or skill score, and PS-2/PS-3 when they
    arrive.

    The direction is taken from the metric's own declaration where the run recorded one, and
    otherwise measured: the ``uncorrelated`` anchor is by construction as bad as a field can
    look, so an anchor below the clean value means larger is better. Measuring is the fallback
    rather than the primary source because the anchor is empty for a metric invariant to the
    translation it is built from -- the case the degeneracy guard above exists for.

    Returns:
        ``{(dataset, metric, field): +1 or -1}``. Missing keys mean ``+1``.
    """
    keys = ["dataset", "metric", "field"]
    out: dict[tuple, int] = {}

    if "higher_is_better" in df.columns:
        declared = df.groupby(keys, observed=True)["higher_is_better"].agg(
            lambda s: bool(s.iloc[0])
        )
        for key, higher in declared.items():
            out[key] = -1 if higher else 1

    anchors = norm if norm is not None else normalisation(df)
    for _, row in anchors.iterrows():
        key = (row["dataset"], row["metric"], row["field"])
        if key in out:
            continue                      # a declaration outranks an inference
        clean, high = row["value_clean"], row["value_uncorrelated"]
        if row["degenerate"] or not (np.isfinite(clean) and np.isfinite(high)):
            continue                      # no usable anchor: leave it at the default
        out[key] = -1 if high < clean else 1
    return out


# --- per-axis criteria ------------------------------------------------------------------


def summarise_axes(df: pd.DataFrame, *, norm: pd.DataFrame | None = None,
                   block_length: int = 10, n_bootstrap: int = 200,
                   seed: int = 0) -> pd.DataFrame:
    """One row per (dataset, metric, field, ladder axis) with the criteria of group A.

    Args:
        df: The tidy result frame, with or without a ``damage`` column.
        norm: Normalisation anchors. When given, the sensitivity and saturation levels are
            measured against the shared clean-to-unrelated span, which makes them
            comparable across axes; without it each axis is measured against its own
            range and the numbers mean different things on different rows.
        block_length: Moving-block bootstrap block length, in frames. The metric trace is
            autocorrelated in time, so an independent bootstrap would give absurdly tight
            intervals.
        n_bootstrap: Bootstrap resamples.
        seed: Bootstrap seed.
    """
    rng = np.random.default_rng(seed)
    reference = df[df["level"] == 0]
    directions = response_direction(df, norm)
    spans = (
        norm.set_index(["dataset", "metric", "field"])["span"].to_dict()
        if norm is not None else {}
    )
    rows = []

    # Severity levels that resolved to the same experiment as a milder one are not independent
    # points. Scoring a tie would read as agreement in the rank correlation and would compare a
    # distribution against itself in the separability, so they are dropped and counted.
    ladder = df[df["level"] > 0]
    n_dropped = 0
    if "severity_degenerate" in ladder.columns:
        degenerate = ladder["severity_degenerate"].fillna(False).astype(bool)
        n_dropped = int(degenerate.sum())
        ladder = ladder[~degenerate]
        if n_dropped:
            log.info(
                "excluded %d rows on severity levels that resolved to a milder "
                "severity level's severity; "
                "n_levels below is what was measured, n_levels_configured what was asked for",
                n_dropped,
            )

    for (dataset, metric, field, axis), g in ladder.groupby(
        ["dataset", "metric", "field", "degradation"], observed=True
    ):
        levels = g["level"].to_numpy()
        values = g["value"].to_numpy()
        is_probe = axis in PROBE_LABELS
        # Every ordering statistic below is computed on the value multiplied by this sign, so
        # "rises with damage" holds by construction and the four of them need no direction
        # argument. The reported values stay in the metric's own units.
        sign = directions.get((dataset, metric, field), 1)
        target = _declared_target(g)
        if target is None:
            oriented = g.assign(value=sign * g["value"])
        else:
            # A metric calibrated at an interior point is not monotone in damage: it is
            # wrong above the target and equally wrong below it. Ordering by distance
            # from the target is what makes the one-sided statistics mean what they say.
            oriented = g.assign(value=_target_distance(g["value"], target))
            sign = 1
        clean = float(
            reference[
                (reference["dataset"] == dataset)
                & (reference["metric"] == metric)
                & (reference["field"] == field)
            ]["value"].median()
        )
        # The clean value on the same scale the ordering statistics run on. For an
        # ordinary metric that is just the sign applied; for a target-valued one it is
        # the distance from the target, which is near zero for a calibrated prediction.
        oriented_clean = (
            sign * clean if target is None
            else float(_target_distance(pd.Series([clean]), target).iloc[0])
        )

        record: dict[str, object] = {
            "dataset": dataset,
            "metric": metric,
            "field": field,
            "degradation": axis,
            "degradation_family": g["degradation_family"].iloc[0],
            "is_probe": is_probe,
            "n_levels": int(g["level"].nunique()),
            "n_levels_configured": int(
                df[(df["field"] == field) & (df["degradation"] == axis)]["level"].nunique()
            ),
            "n_frames": int(g["frame_index"].nunique()),
            "value_clean": clean,
            "value_min": float(values.min()),
            "value_max": float(values.max()),
            "cost_s": float(g["wall_time_s"].mean()),
            "higher_is_better": sign < 0,
        }

        if is_probe or g["level"].nunique() < 2:
            record.update(
                rho=np.nan, rho_frame_min=np.nan, rho_pooled=np.nan,
                rho_ci_lo=np.nan, rho_ci_hi=np.nan,
                monotone_fraction=np.nan, separability_auc_min=np.nan,
                sensitivity_level=np.nan, saturation_level=np.nan,
            )
        else:
            per_frame = _per_frame_rho(oriented)
            lo, hi = _block_bootstrap_rho(oriented, rng, block_length, n_bootstrap)
            # An all-NaN per-frame correlation is a documented outcome, not a surprise: it is
            # what a metric invariant to this axis produces once the round-off guard has done
            # its job. Suppressed here so it does not read as a numerical accident.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                rho_median = float(np.nanmedian(per_frame)) if len(per_frame) else np.nan
                rho_worst = float(np.nanmin(per_frame)) if len(per_frame) else np.nan
            record.update(
                rho=rho_median,
                rho_frame_min=rho_worst,
                rho_pooled=(
                    np.nan if _is_round_off(values)
                    else float(
                        spearmanr(levels, oriented["value"].to_numpy()).statistic
                        if target is not None
                        else sign * spearmanr(levels, values).statistic
                    )
                ),
                rho_ci_lo=lo,
                rho_ci_hi=hi,
                monotone_fraction=_monotone_fraction(oriented),
                separability_auc_min=_min_adjacent_auc(oriented),
                # Thresholds compare against the clean severity level on whatever scale the
                # ordering statistics run on, so a target-valued metric measures its
                # departure from *calibration* rather than from a raw ratio.
                sensitivity_level=_threshold_level(
                    oriented, oriented_clean, SENSITIVITY_FRACTION,
                    _signed(spans.get((dataset, metric, field)), sign)),
                saturation_level=_threshold_level(
                    oriented, oriented_clean, SATURATION_FRACTION,
                    _signed(spans.get((dataset, metric, field)), sign)),
            )
        if "damage" in g.columns:
            damage = g["damage"].to_numpy()
            # All-NaN whenever the anchor is degenerate, which is the documented outcome for a
            # metric that cannot tell the unrelated field from the reference.
            record["damage_max"] = (
                float(np.nanmax(damage)) if np.isfinite(damage).any() else np.nan
            )
        rows.append(record)

    return pd.DataFrame(rows)


def _signed(span: float | None, sign: int) -> float | None:
    """Orient a shared span, so a threshold on oriented values uses an oriented target."""
    return None if span is None else sign * span


def _per_frame_rho(g: pd.DataFrame) -> np.ndarray:
    """Spearman correlation between severity level and value, computed separately in each frame.

    **This is the primary statistic, not the pooled one.** Pooling every (level, value)
    pair across frames conflates the metric's response to severity with any trend in the
    field itself, and on this data that ruins it: the density perturbation grows six orders
    of magnitude along the trajectory, so the worst severity level early is far smaller than the
    mildest severity level late. Measured consequence -- every density axis is perfectly ordered
    inside every frame, yet the pooled correlation reads between 0.10 and 0.91 depending on
    the axis. The pooled value is retained as ``rho_pooled`` for comparison, since a wide
    gap between the two is itself a signal that the field is non-stationary.
    """
    out = []
    for _, sub in g.groupby("frame_index", observed=True):
        if sub["level"].nunique() < 2:
            continue
        if _is_round_off(sub["value"].to_numpy()):
            out.append(np.nan)
            continue
        out.append(spearmanr(sub["level"], sub["value"]).statistic)
    return np.asarray(out, dtype=float)


def _is_round_off(values: np.ndarray) -> bool:
    """Whether a set of values differs by no more than floating-point noise.

    A rank correlation is defined for any values that are not exactly tied, and float64
    arithmetic almost never ties exactly: ``np.roll`` cannot change a translation-invariant
    quantity, but it does change the summation order inside ``np.mean``, so the severity levels come
    out differing in the last bits and in an arbitrary order. Ranking that gives a number.

    Reproduced end to end -- ``evaluate.py metrics=[enstrophy]`` with a translation-only ladder
    reported ``rho_min = 0.707`` on ``translate_x`` from values spanning a relative 1.6e-16,
    printed in the monotonicity heatmap beside genuine correlations and indistinguishable from
    them.
    """
    finite = values[np.isfinite(values)]
    if len(finite) < 2:
        return True
    scale = float(np.max(np.abs(finite)))
    if scale == 0.0:
        return True          # every value is exactly zero: no ordering to measure
    return bool(float(np.ptp(finite)) < DEGENERATE_SPAN * scale)


def _monotone_fraction(g: pd.DataFrame) -> float:
    """Fraction of frames on which the severity level ordering is strictly correct.

    A metric can look fine pooled and be non-monotone within every individual frame, which
    a single correlation hides.
    """
    ok = 0
    frames = g["frame_index"].unique()
    for frame in frames:
        sub = g[g["frame_index"] == frame].sort_values("level")
        if np.all(np.diff(sub["value"].to_numpy()) > 0):
            ok += 1
    return ok / len(frames) if len(frames) else float("nan")


def _min_adjacent_auc(g: pd.DataFrame) -> float:
    """Smallest Mann-Whitney AUC between adjacent severity levels' distributions over time.

    Monotone medians are not enough: if adjacent severity levels overlap, the metric cannot rank two
    models that differ by one severity level. Reported as a descriptive overlap measure only -- no
    p-value, because the trace is autocorrelated and any independence-assuming test would
    be badly anti-conservative.
    """
    levels = sorted(g["level"].unique())
    if len(levels) < 2:
        return float("nan")
    aucs = []
    for a, b in pairwise(levels):
        xa = g.loc[g["level"] == a, "value"].to_numpy()
        xb = g.loc[g["level"] == b, "value"].to_numpy()
        if len(xa) < 2 or len(xb) < 2:
            continue
        u = mannwhitneyu(xb, xa, alternative="greater").statistic
        aucs.append(u / (len(xa) * len(xb)))
    return float(min(aucs)) if aucs else float("nan")


def _threshold_level(g: pd.DataFrame, clean: float, fraction: float,
                     shared_span: float | None = None) -> float:
    """First level whose median reaches ``fraction`` of the way to the unrelated limit.

    Measured against the shared span when one is available, so "fires at severity level 2" means the
    same thing on every axis. Falling back to each axis's own range would make an axis that
    barely damages the field appear just as sensitive as one that destroys it.
    """
    medians = g.groupby("level", observed=True)["value"].median().sort_index()
    if medians.empty:
        return float("nan")
    if _is_round_off(medians.to_numpy()):
        # The level at which a metric "first departs from clean" is not defined when it never
        # departs. Without this the answer is always severity level 1, because any target built from
        # a round-off span is cleared by round-off: measured on enstrophy against a translation-only
        # ladder, both the sensitivity and saturation levels read 1.0 for a quantity translation
        # cannot change at all. Same principle as the rank-correlation guard.
        return float("nan")
    span = shared_span if shared_span is not None else float(medians.iloc[-1]) - clean
    if span is None or not np.isfinite(span) or span == 0:
        return float("nan")
    target = clean + fraction * span
    reached = medians[medians >= target]
    return float(reached.index[0]) if len(reached) else float("nan")


def _block_bootstrap_rho(
    g: pd.DataFrame, rng: np.random.Generator, block_length: int, n: int
) -> tuple[float, float]:
    """Percentile interval for the per-frame Spearman median, over blocks of frames.

    Blocks rather than individual frames because the metric trace is autocorrelated;
    resampling frames independently would understate the interval by a large factor.
    """
    frames = np.sort(g["frame_index"].unique())
    if len(frames) < 2 * block_length or n <= 0:
        return (float("nan"), float("nan"))
    block_length = max(1, min(block_length, len(frames) // 2))
    n_blocks = int(np.ceil(len(frames) / block_length))
    starts = np.arange(len(frames) - block_length + 1)
    by_frame = {f: g[g["frame_index"] == f] for f in frames}

    # Resample the PER-FRAME statistic, matching what `rho` reports.
    per_frame = {
        f: spearmanr(sub["level"], sub["value"]).statistic
        for f, sub in ((f, by_frame[f]) for f in frames)
        if sub["level"].nunique() >= 2
    }
    if not per_frame:
        return (float("nan"), float("nan"))

    draws = []
    for _ in range(n):
        chosen = rng.choice(starts, size=n_blocks)
        picked = np.concatenate([frames[s: s + block_length] for s in chosen])
        values = [per_frame[f] for f in picked if f in per_frame]
        if values:
            draws.append(float(np.nanmedian(values)))
    if not draws:
        return (float("nan"), float("nan"))
    return (float(np.nanpercentile(draws, 5)), float(np.nanpercentile(draws, 95)))


# --- probes --------------------------------------------------------------------------


def probe_summary(df: pd.DataFrame, norm: pd.DataFrame) -> pd.DataFrame:
    """One row per (dataset, metric, field) for the non-monotone probes.

    Reports the IN-4 damage score alongside the ladder severity level whose damage is closest, which
    is what makes it interpretable: "the Gaussian field looks as bad as coarsening to 64".

    A group that ran no probe contributes no row. The probes are ordinary ladder entries
    and a custom ladder may omit them -- the ensemble miscalibration ladder does, since a
    phase-scrambled field says nothing about whether an ensemble is honestly dispersed.
    Emitting a row carrying only the group keys made the card generator write a trap-test
    line with an em dash for its score, which a reader cannot distinguish from a trap test
    that ran and could not be scored.
    """
    scored = add_damage(df, norm)
    rows = []
    for (dataset, metric, field), g in scored.groupby(
        ["dataset", "metric", "field"], observed=True
    ):
        record = {"dataset": dataset, "metric": metric, "field": field}
        present = sorted(PROBE_LABELS & set(g["degradation"].unique()))
        if not present:
            continue
        for label in present:
            sub = g[g["degradation"] == label]
            damage = float(sub["damage"].median())
            record[f"{label}_value"] = float(sub["value"].median())
            record[f"{label}_damage"] = damage
            if label != UNCORRELATED_LABEL:
                # The anchor's nearest severity level is the largest translation by construction,
                # so reporting it would add a column that carries no information.
                record[f"{label}_nearest_level"] = _nearest_level(g, damage, exclude=label)
        rows.append(record)
    if not rows:
        # Empty, but still carrying the group keys: every consumer filters this frame by
        # metric or field before reading it, and a frame with no columns at all raises a
        # KeyError on that filter rather than returning nothing.
        return pd.DataFrame(columns=["dataset", "metric", "field"])
    return pd.DataFrame(rows)


def _nearest_level(g: pd.DataFrame, damage: float, exclude: str) -> str:
    """The ordinal severity level whose damage is closest to ``damage``, for interpretation."""
    ordinal = g[(~g["degradation"].isin(PROBE_LABELS)) & (g["level"] > 0)]
    if ordinal.empty or not np.isfinite(damage):
        return ""
    medians = ordinal.groupby(["degradation", "level", "severity"], observed=True)[
        "damage"
    ].median()
    if medians.empty:
        return ""
    label, _level, severity = medians.sub(damage).abs().idxmin()
    return f"{label}={severity:g}"


# --- roll-up and flagging ---------------------------------------------------------------


def report_card(axes: pd.DataFrame, probes: pd.DataFrame,
                norm: pd.DataFrame) -> pd.DataFrame:
    """One row per (dataset, metric, field): the criteria gathered for reading.

    Deliberately has no verdict column. It carries the measurements; :func:`flag` adds an
    advisory ``flags`` string, and the decision is made by people.
    """
    ordinal = axes[~axes["is_probe"]]
    keys = ["dataset", "metric", "field"]
    if ordinal.empty:
        base = axes[keys].drop_duplicates()
    else:
        base = (
            ordinal.groupby(keys, observed=True)
            .agg(
                n_axes=("degradation", "nunique"),
                rho_min=("rho", "min"),
                rho_median=("rho", "median"),
                rho_pooled_min=("rho_pooled", "min"),
                separability_auc_min=("separability_auc_min", "min"),
                monotone_fraction_min=("monotone_fraction", "min"),
                sensitivity_level_median=("sensitivity_level", "median"),
                saturation_level_median=("saturation_level", "median"),
                cost_s=("cost_s", "mean"),
            )
            .reset_index()
        )
        # ``idxmin`` raises on an all-NA group rather than returning NA, and a group is
        # all-NA whenever a metric is exactly invariant to every ordinal operator in the
        # ladder -- a single-field invariant against a translation-only ladder, say. That is a
        # legitimate configuration which AGENTS.md explicitly calls correct, and it used to
        # take down the whole report with a pandas message naming nothing in this codebase,
        # after the expensive evaluation had already been paid for.
        rho_defined = ordinal[ordinal["rho"].notna()]
        if rho_defined.empty:
            base["worst_axis"] = pd.NA
        else:
            worst = rho_defined.loc[
                rho_defined.groupby(keys, observed=True)["rho"].idxmin()
            ][[*keys, "degradation"]].rename(columns={"degradation": "worst_axis"})
            base = base.merge(worst, on=keys, how="left")

    for extra in (probes, norm[[*keys, "value_clean", "value_uncorrelated", "span",
                                "anchor_source", "degenerate"]]):
        if not extra.empty:
            base = base.merge(extra, on=keys, how="left")

    if "cost_s" in base.columns and not base.empty:
        baseline = base["cost_s"].min()
        base["cost_relative"] = base["cost_s"] / baseline if baseline else np.nan
    return base


def flag(card: pd.DataFrame, thresholds: Mapping[str, float]) -> pd.DataFrame:
    """Add an advisory ``flags`` column naming which reference thresholds were not met.

    Separate from the computation on purpose. An empty ``flags`` means nothing was
    flagged, **not** that the metric is approved; the thresholds are reference values for
    drawing attention, not acceptance criteria.
    """
    out = card.copy()
    checks: list[tuple[str, str, float, bool]] = [
        ("rho_min", "spearman", thresholds.get("spearman", np.nan), True),
        ("separability_auc_min", "separability_auc",
         thresholds.get("separability_auc", np.nan), True),
        ("gaussian_impostor_damage", "impostor_damage",
         thresholds.get("impostor_damage", np.nan), True),
    ]
    messages = []
    for _, row in out.iterrows():
        notes = []
        for column, name, limit, below_is_flagged in checks:
            if column not in out.columns or not np.isfinite(limit):
                continue
            value = row.get(column)
            if value is None or not np.isfinite(value):
                continue
            if (value < limit) if below_is_flagged else (value > limit):
                notes.append(f"{name}={value:.2f} < {limit:g}")
        if bool(row.get("degenerate", False)):
            notes.append("no dynamic range")
        messages.append("; ".join(notes))
    out["flags"] = messages
    return out


# --- cross-metric ------------------------------------------------------------------------


def cross_metric_correlation(df: pd.DataFrame, *, field: str | None = None) -> pd.DataFrame:
    """Spearman correlation between metrics across the ladder, for pruning.

    One observation per (axis, level), using the median over time, which is the level at
    which the panel decision is actually made. Using every raw row instead would inflate
    the correlation through shared time trends.

    The reference severity level is excluded. Every pairwise error metric is exactly zero there, so
    keeping it would add a point all metrics share by construction and pull every
    correlation towards +1.
    """
    sub = df if field is None else df[df["field"] == field]
    sub = sub[sub["level"] > 0]
    pivot = (
        sub.groupby(["degradation", "level", "metric"], observed=True)["value"]
        .median()
        .unstack("metric")
        .dropna(how="any")
    )
    if pivot.shape[1] < 2 or len(pivot) < 3:
        return pd.DataFrame()
    rho = pivot.corr(method="spearman")
    rho.index.name = "metric"
    return rho


def selectivity_profile(axes: pd.DataFrame) -> pd.DataFrame:
    """Rank correlation per metric against every ladder axis: what a metric detects.

    Read across a row rather than down a column. Two metrics with near-identical profiles
    are redundant even when their magnitudes differ, and a profile that is uniform across
    every axis indicates a metric responding to damage in general rather than to a
    specific failure mode.
    """
    ordinal = axes[~axes["is_probe"]]
    if ordinal.empty:
        return pd.DataFrame()
    return (
        ordinal.pivot_table(index=["metric", "field"], columns="degradation",
                            values="rho", observed=True)
        .reset_index()
    )
