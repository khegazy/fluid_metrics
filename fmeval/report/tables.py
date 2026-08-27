"""Table renderers.

Every table is written twice: a CSV in ``data/`` as the machine-readable source, and a
booktabs float in ``tables/`` as the typeset form. No number appears in the document
without a CSV beside it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .context import TableResult
from .registry import table


@table(
    section=2, order=10, scope="global",
    title="Summary",
    requires_columns=("value",),
)
def report_card(ctx, df, opts) -> TableResult:
    """The criteria gathered into one row per metric and field.

    Deliberately has no verdict column. The ``flags`` entry names which configured
    reference values were not met, so a row can be found quickly; an empty entry means
    nothing was flagged, not that the metric is approved.
    """
    ctx.require(not ctx.card.empty, "no summary rows")
    columns = [
        ("metric", "metric"), ("field", "field"),
        ("n_axes", "axes"), ("rho_min", "worst rho"), ("worst_axis", "worst axis"),
        ("separability_auc_min", "min AUC"),
        ("gaussian_impostor_damage", "Gaussian field"),
        ("sensitivity_level_median", "fires at"),
        ("saturation_level_median", "saturates at"),
        ("cost_relative", "rel. cost"),
        ("flags", "flags"),
    ]
    present = [(c, h) for c, h in columns if c in ctx.card.columns]
    frame = ctx.card[[c for c, _ in present]].copy()
    return TableResult(
        frame=frame,
        caption="Measured criteria for each metric and field. The flags column names the "
                "configured reference values a row did not meet; it is an aid to reading, "
                "not a judgement.",
        headers=dict(present),
        formats={"metric": "code", "field": "code", "worst_axis": "code",
                 "flags": "%s"},
        note="Rank correlation is computed within each ladder axis and never across; the "
             "reported value is the minimum over axes.",
    )


@table(
    section=4, order=20, scope="per_field",
    title="Per-axis detail",
    requires_columns=("degradation", "level", "value"),
)
def axis_detail(ctx, df, opts) -> TableResult:
    """Every criterion for every metric and ladder axis, with the bootstrap interval."""
    field = str(df["field"].iloc[0])
    rows = ctx.axes[(ctx.axes["field"] == field) & (~ctx.axes["is_probe"])].copy()
    ctx.require(not rows.empty, f"no ordinal axes for {field}")
    rows = rows.sort_values(["metric", "rho"])
    keep = ["metric", "degradation", "n_levels", "rho", "rho_frame_min",
            "rho_pooled", "rho_ci_lo", "rho_ci_hi", "monotone_fraction",
            "separability_auc_min", "sensitivity_level", "saturation_level"]
    return TableResult(
        frame=rows[[c for c in keep if c in rows.columns]],
        keys={"field": field},
        caption=f"Per-axis criteria on {field}. Rank correlation is computed within each "
                "frame and the median reported, because pooling across frames conflates "
                "the response to severity with any trend in the field itself. The pooled "
                "value is shown for comparison; a large gap between the two indicates a "
                "non-stationary field rather than a defective metric. The interval is a "
                "moving-block bootstrap over frames, which accounts for the "
                "autocorrelation of the trace in time.",
        headers={"degradation": "axis", "n_levels": "severity levels", "rho": "rho",
                 "rho_frame_min": "rho worst frame", "rho_pooled": "rho pooled",
                 "rho_ci_lo": "CI low", "rho_ci_hi": "CI high",
                 "monotone_fraction": "frames ordered",
                 "separability_auc_min": "min AUC",
                 "sensitivity_level": "fires at", "saturation_level": "saturates at"},
        formats={"metric": "code", "degradation": "code"},
    )


@table(
    section=8, order=20, scope="global",
    title="Misleading fields",
    requires_columns=("damage",),
    requires_degradations=("gaussian_impostor",),
)
def deception_table(ctx, df, opts) -> TableResult:
    """Values assigned to the deliberately misleading fields.

    The nearest ordinary severity level makes the damage figure interpretable: it says which
    ordinary degradation the metric considers equally bad.
    """
    ctx.require(not ctx.probes.empty, "no probe rows")
    frame = ctx.probes.copy()
    keep = [c for c in (
        "metric", "field",
        "gaussian_impostor_value", "gaussian_impostor_damage",
        "gaussian_impostor_nearest_level",
        "uncorrelated_value", "uncorrelated_damage",
    ) if c in frame.columns]
    return TableResult(
        frame=frame[keep],
        caption="Response to fields built to mislead. The spectrum-matched Gaussian field "
                "preserves the energy spectrum and two-point correlation exactly while "
                "removing all phase information. The unrelated field preserves every "
                "statistic while removing alignment, and therefore defines a damage of 1.",
        headers={"gaussian_impostor_value": "Gaussian value",
                 "gaussian_impostor_damage": "Gaussian damage",
                 "gaussian_impostor_nearest_level": "equivalent severity level",
                 "uncorrelated_value": "unrelated value",
                 "uncorrelated_damage": "unrelated damage"},
        formats={"metric": "code", "field": "code",
                 "gaussian_impostor_nearest_level": "code"},
        note="A damage near 1 for the unrelated field is expected by construction: it is "
             "the measurement that sets the scale.",
    )


@table(
    section=10, order=10, scope="global",
    title="Cost",
    requires_columns=("wall_time_s",),
)
def cost_table(ctx, df, opts) -> TableResult:
    """Wall clock per evaluation and its projection to a full trajectory."""
    stats = (
        df.groupby(["metric", "field"], observed=True)["wall_time_s"]
        .agg(median="median", p95=lambda s: s.quantile(0.95))
        .reset_index()
    )
    n_frames = int(ctx.meta.get("n_frames", 0)) or int(df["frame_index"].nunique())
    n_variants = int(df["variant_label"].nunique())
    stats["per_frame_s"] = stats["median"] * n_variants
    stats["full_trajectory_s"] = stats["per_frame_s"] * 10001
    baseline = stats["median"].min()
    stats["relative"] = stats["median"] / baseline if baseline else np.nan
    return TableResult(
        frame=stats,
        caption="Metric evaluation cost, excluding input and degradation. The projection "
                "assumes a 10001-frame trajectory at the present ladder width "
                f"({n_variants} variants per frame), which is the number that decides "
                "whether a metric is usable on a full rollout.",
        headers={"median": "median [s]", "p95": "p95 [s]",
                 "per_frame_s": "per frame [s]",
                 "full_trajectory_s": "full trajectory [s]",
                 "relative": "relative"},
        formats={"metric": "code", "field": "code"},
        note=f"Measured over {n_frames} frames.",
    )


@table(
    section=7, order=20, scope="global", min_metrics=2,
    title="Cross-metric correlation",
    requires_columns=("value",),
)
def redundancy_table(ctx, df, opts) -> TableResult:
    """Rank correlation between metrics across the ladder, for pruning the panel.

    One observation per axis and severity level, using the median over frames. The reference
    severity level is excluded: every pairwise error metric is exactly zero there, so keeping it
    would add a point all metrics share by construction.
    """
    from fmeval.analysis import cross_metric_correlation

    rho = cross_metric_correlation(df)
    ctx.require(not rho.empty, "needs at least two metrics with common ladder severity levels")
    limit = float(ctx.thresholds.get("redundancy", 0.95))
    frame = rho.reset_index()
    pairs = [
        f"{a}/{b}"
        for i, a in enumerate(rho.index)
        for b in rho.index[i + 1:]
        if np.isfinite(rho.loc[a, b]) and abs(rho.loc[a, b]) >= limit
    ]
    return TableResult(
        frame=frame,
        caption="Spearman correlation between metrics across the ladder.",
        formats={"metric": "code"},
        note=(f"Pairs at or above {limit:g}: {', '.join(pairs)}." if pairs
              else f"No pair reaches {limit:g}."),
    )


@table(
    section=11, order=10, scope="global",
    title="Run provenance",
    requires_columns=("value",),
)
def provenance_table(ctx, df, opts) -> TableResult:
    """Everything needed to reproduce these numbers."""
    meta = ctx.meta
    git = meta.get("git", {}) or {}
    entries = [
        ("metric", meta.get("metric", "")),
        ("dataset", meta.get("dataset", "")),
        ("frames", meta.get("n_frames", "")),
        ("fields", ", ".join(meta.get("fields", []) or [])),
        ("analysis grid", meta.get("analysis_grid", "")),
        ("ladder axes", len(meta.get("ladder_axes", []) or [])),
        ("severity levels", meta.get("n_severity_levels", "")),
        ("seed", meta.get("seed", "")),
        ("config hash", meta.get("config_hash", "")),
        ("git commit", (git.get("sha") or "")[:12]),
        ("git dirty", git.get("dirty", "")),
        ("host", meta.get("host", "")),
        ("python", meta.get("python", "")),
    ]
    return TableResult(
        frame=pd.DataFrame(entries, columns=["item", "value"]),
        caption="Provenance of this run.",
        formats={"value": "code"},
        note="The full resolved configuration follows below, and is also written to "
             "data/config.yaml.",
    )


#: Absolute gap between a requested energy fraction and the realised one, above which the report
#: says so. Not a threshold on acceptance -- the severity level is a real experiment either way --
#: only on whether its nominal severity describes it honestly.
MISSED_REQUEST = 0.15


@table(
    section=11, order=5, scope="global",
    title="Resolved ladder severities",
    requires_columns=("field", "degradation", "level", "severity", "severity_nominal",
                      "calibration", "energy_removed", "energy_changed"),
)
def calibrated_severities_table(ctx, df, opts) -> TableResult:
    """What each calibrated config severity became on each field.

    A calibrated axis is uninterpretable without this. The config asks for a fraction -- of the
    field's characteristic scale, or of the energy a filter removes -- and the harness resolves it
    per field against a measured spectrum, so the same config number is a different width or
    cutoff on a smooth field than on a broadband one. That is the point of calibrating, and it
    means the absolute numbers in the rest of the report belong to this table.

    The last two columns are what the severity level *measurably did*, which is not the same as what
    it asked
    for. A cutoff must land on an available set of modes, so where a field's energy is concentrated
    the realised removal jumps rather than following the request: 69% of density's fluctuation
    energy is in the four diagonal modes at |k| = sqrt(2) and 3e-5 of it below them, so two
    consecutive cutoffs there differ by most of the field. Without these columns a reader cannot
    tell a severity level that did what was asked from one that overshot to the next set of modes.
    """
    calibrated = df[df["calibration"].astype(str).ne("") & (df["level"] > 0)]
    ctx.require(len(calibrated) > 0, "no calibrated axis in this run")

    rows = []
    for (field, axis, level), g in calibrated.groupby(
        ["field", "degradation", "level"], observed=True
    ):
        rows.append({
            "field": str(field),
            "axis": str(axis),
            "relative to": str(g["calibration"].iloc[0]),
            "level": int(level),
            "configured": float(g["severity_nominal"].iloc[0]),
            "applied": float(g["severity"].iloc[0]),
            "energy removed": float(g["energy_removed"].median()),
            "energy changed": float(g["energy_changed"].median()),
            "used": "no" if bool(g["severity_degenerate"].iloc[0]) else "yes",
        })
    frame = pd.DataFrame(rows).sort_values(["field", "axis", "level"])

    # A severity level can be a perfectly valid experiment and still not be the one that was
    # requested.
    # A cutoff selects whole sets of modes, so where a field's energy is concentrated the nearest
    # available cutoff can remove far more or far less than the fraction asked for. That is worth
    # naming, because the nominal severity is what appears on every axis label in the report.
    spectral = frame[frame["relative to"].str.startswith("energy")]
    missed = spectral[
        (spectral["energy removed"] - spectral["configured"]).abs() > MISSED_REQUEST
    ]

    dropped = frame[frame["used"] == "no"]
    if len(dropped):
        note = (
            f"{len(dropped)} of {len(frame)} severity_levels resolved either onto a "
            "milder severity_level's "
            "severity or onto a severity at which the operator does nothing, and are excluded "
            "from the acceptance statistics. That is a limit of the field rather than a "
            "misconfiguration: a sharp filter acts on whole wavenumber shells and a windowed "
            "kernel on an odd number of cells, so a field holding its energy in a few "
            "wavenumbers cannot support as many distinct severity levels as the config requests."
        )
    else:
        note = "Every configured severity level resolved to a distinct experiment on every field."

    if len(missed):
        worst = ", ".join(
            f"{r['field']}/{r['axis']} level {r['level']} asked for "
            f"{r['configured']:.2f} and removed {r['energy removed']:.3f}"
            for _, r in missed.sort_values("level").iterrows()
        )
        note += (
            f" {len(missed)} spectral severity_level(s) removed a fraction differing "
            "from the request by "
            f"more than {MISSED_REQUEST:g}, because a cutoff selects whole sets of modes and the "
            "nearest available one was not close: " + worst + ". These are still valid "
            "experiments, but their nominal severity understates or overstates what they did."
        )

    return TableResult(
        frame=frame,
        caption="Configured (relative) against applied (absolute) severity and the realised "
                "effect, per field.",
        formats={"field": "code", "axis": "code", "relative to": "code"},
        headers={"energy removed": "energy removed", "energy changed": "energy changed"},
        note=note,
        notes=[
            "\\emph{energy removed} is $1 - \\mathrm{var}(\\text{degraded}) / "
            "\\mathrm{var}(\\text{reference})$ and \\emph{energy changed} is "
            "$\\langle(\\text{degraded}-\\text{reference})^2\\rangle / "
            "\\mathrm{var}(\\text{reference})$, both about the spatial mean and both "
            "medians over frames. For a filter the first is exactly the fraction of energy it "
            "deleted; it is near zero for an operator that relocates energy rather than removing "
            "it, and negative for one that adds energy.",
        ],
    )
