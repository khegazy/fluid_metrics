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
declaration. It is a separate probe, not a rung.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

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


# --- normalisation --------------------------------------------------------------------


def normalisation(df: pd.DataFrame,
                  *, uncorrelated_label: str = UNCORRELATED_LABEL) -> pd.DataFrame:
    """Anchors that put every metric on one dimensionless scale.

    Raw mean squared error and a raw transport distance are not comparable, so a *damage
    score* is defined per (dataset, metric, field):

        D = (v - clean) / (uncorrelated - clean)

    ``clean`` is the median value on the reference rung. ``uncorrelated`` is *measured*,
    not inferred: the ``uncorrelated`` ladder entry applies several large random
    translations, which preserve every statistic exactly while destroying alignment, and
    the metric is evaluated against those. D = 1 then means "as different as two unrelated
    fields", which is what makes the score readable across metrics with different units.

    Scavenging the largest configured translation rung instead would understate the anchor
    badly: on the real data a 16-cell displacement only reaches about 0.6 of the true
    uncorrelated value, so every damage score would be inflated by roughly 1.6x.

    A ratio to the clean value is not usable here: mean squared error on the reference rung
    is exactly zero. Per-figure min-max scaling is not usable either, because the figure
    would change whenever a rung is added.

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
        scale = float(np.nanmedian(np.abs(g["value"]))) or 1.0
        rows.append(
            {
                "dataset": dataset,
                "metric": metric,
                "field": field,
                "value_clean": clean,
                "value_uncorrelated": high,
                "span": span,
                "anchor_source": source,
                "degenerate": not np.isfinite(span) or abs(span) < 1e-12 * scale,
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

    # Otherwise fall back to the worst rung of any ordinal axis, and say so.
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


# --- per-axis criteria ------------------------------------------------------------------


def summarise_axes(df: pd.DataFrame, *, block_length: int = 10,
                   n_bootstrap: int = 200, seed: int = 0) -> pd.DataFrame:
    """One row per (dataset, metric, field, ladder axis) with the criteria of group A.

    Args:
        df: The tidy result frame, with or without a ``damage`` column.
        block_length: Moving-block bootstrap block length, in frames. The metric trace is
            autocorrelated in time, so an independent bootstrap would give absurdly tight
            intervals.
        n_bootstrap: Bootstrap resamples.
        seed: Bootstrap seed.
    """
    rng = np.random.default_rng(seed)
    reference = df[df["level"] == 0]
    rows = []

    for (dataset, metric, field, axis), g in df[df["level"] > 0].groupby(
        ["dataset", "metric", "field", "degradation"], observed=True
    ):
        levels = g["level"].to_numpy()
        values = g["value"].to_numpy()
        is_probe = axis in PROBE_LABELS
        clean = float(
            reference[
                (reference["dataset"] == dataset)
                & (reference["metric"] == metric)
                & (reference["field"] == field)
            ]["value"].median()
        )

        record: dict[str, object] = {
            "dataset": dataset,
            "metric": metric,
            "field": field,
            "degradation": axis,
            "degradation_family": g["degradation_family"].iloc[0],
            "is_probe": is_probe,
            "n_levels": int(g["level"].nunique()),
            "n_frames": int(g["frame_index"].nunique()),
            "value_clean": clean,
            "value_min": float(values.min()),
            "value_max": float(values.max()),
            "cost_s": float(g["wall_time_s"].mean()),
        }

        if is_probe or g["level"].nunique() < 2:
            record.update(
                rho=np.nan, rho_ci_lo=np.nan, rho_ci_hi=np.nan,
                monotone_fraction=np.nan, separability_auc_min=np.nan,
                sensitivity_level=np.nan, saturation_level=np.nan,
            )
        else:
            rho = float(spearmanr(levels, values).statistic)
            lo, hi = _block_bootstrap_rho(g, rng, block_length, n_bootstrap)
            record.update(
                rho=rho,
                rho_ci_lo=lo,
                rho_ci_hi=hi,
                monotone_fraction=_monotone_fraction(g),
                separability_auc_min=_min_adjacent_auc(g),
                sensitivity_level=_threshold_level(g, clean, SENSITIVITY_FRACTION),
                saturation_level=_threshold_level(g, clean, SATURATION_FRACTION),
            )
        if "damage" in g.columns:
            record["damage_max"] = float(np.nanmax(g["damage"].to_numpy()))
        rows.append(record)

    return pd.DataFrame(rows)


def _monotone_fraction(g: pd.DataFrame) -> float:
    """Fraction of frames on which the rung ordering is strictly correct.

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
    """Smallest Mann-Whitney AUC between adjacent rungs' distributions over time.

    Monotone medians are not enough: if adjacent rungs overlap, the metric cannot rank two
    models that differ by one rung. Reported as a descriptive overlap measure only -- no
    p-value, because the trace is autocorrelated and any independence-assuming test would
    be badly anti-conservative.
    """
    levels = sorted(g["level"].unique())
    if len(levels) < 2:
        return float("nan")
    aucs = []
    for a, b in zip(levels, levels[1:]):
        xa = g.loc[g["level"] == a, "value"].to_numpy()
        xb = g.loc[g["level"] == b, "value"].to_numpy()
        if len(xa) < 2 or len(xb) < 2:
            continue
        u = mannwhitneyu(xb, xa, alternative="greater").statistic
        aucs.append(u / (len(xa) * len(xb)))
    return float(min(aucs)) if aucs else float("nan")


def _threshold_level(g: pd.DataFrame, clean: float, fraction: float) -> float:
    """First level whose median reaches ``fraction`` of the clean-to-worst range."""
    medians = g.groupby("level", observed=True)["value"].median().sort_index()
    if medians.empty:
        return float("nan")
    span = float(medians.iloc[-1]) - clean
    if not np.isfinite(span) or span == 0:
        return float("nan")
    target = clean + fraction * span
    reached = medians[medians >= target]
    return float(reached.index[0]) if len(reached) else float("nan")


def _block_bootstrap_rho(
    g: pd.DataFrame, rng: np.random.Generator, block_length: int, n: int
) -> tuple[float, float]:
    """Percentile interval for Spearman rho, resampling contiguous blocks of frames.

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

    draws = []
    for _ in range(n):
        chosen = rng.choice(starts, size=n_blocks)
        picked = np.concatenate([frames[s: s + block_length] for s in chosen])
        sample = pd.concat([by_frame[f] for f in picked], ignore_index=True)
        if sample["level"].nunique() < 2:
            continue
        draws.append(spearmanr(sample["level"], sample["value"]).statistic)
    if not draws:
        return (float("nan"), float("nan"))
    return (float(np.nanpercentile(draws, 5)), float(np.nanpercentile(draws, 95)))


# --- probes --------------------------------------------------------------------------


def probe_summary(df: pd.DataFrame, norm: pd.DataFrame) -> pd.DataFrame:
    """One row per (dataset, metric, field) for the non-monotone probes.

    Reports the IN-4 damage score alongside the ladder rung whose damage is closest, which
    is what makes it interpretable: "the Gaussian field looks as bad as coarsening to 64".
    """
    scored = add_damage(df, norm)
    rows = []
    for (dataset, metric, field), g in scored.groupby(
        ["dataset", "metric", "field"], observed=True
    ):
        record = {"dataset": dataset, "metric": metric, "field": field}
        for label in sorted(PROBE_LABELS & set(g["degradation"].unique())):
            sub = g[g["degradation"] == label]
            damage = float(sub["damage"].median())
            record[f"{label}_value"] = float(sub["value"].median())
            record[f"{label}_damage"] = damage
            record[f"{label}_nearest_rung"] = _nearest_rung(g, damage, exclude=label)
        rows.append(record)
    return pd.DataFrame(rows)


def _nearest_rung(g: pd.DataFrame, damage: float, exclude: str) -> str:
    """The ordinal rung whose damage is closest to ``damage``, for interpretation."""
    ordinal = g[(~g["degradation"].isin(PROBE_LABELS)) & (g["level"] > 0)]
    if ordinal.empty or not np.isfinite(damage):
        return ""
    medians = ordinal.groupby(["degradation", "level", "severity"], observed=True)[
        "damage"
    ].median()
    if medians.empty:
        return ""
    label, level, severity = medians.sub(damage).abs().idxmin()
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
                rho_min_axis=("rho", lambda s: s.idxmin()),
                separability_auc_min=("separability_auc_min", "min"),
                monotone_fraction_min=("monotone_fraction", "min"),
                sensitivity_level_median=("sensitivity_level", "median"),
                saturation_level_median=("saturation_level", "median"),
                cost_s=("cost_s", "mean"),
            )
            .reset_index()
        )
        worst = ordinal.loc[
            ordinal.groupby(keys, observed=True)["rho"].idxmin().dropna()
        ][[*keys, "degradation"]].rename(columns={"degradation": "worst_axis"})
        base = base.drop(columns=["rho_min_axis"]).merge(worst, on=keys, how="left")

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

    The reference rung is excluded. Every pairwise error metric is exactly zero there, so
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
