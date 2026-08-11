"""Figure renderers.

Each answers one question from the report narrative, and each is registered with the
section it belongs to. Two conventions recur because their absence produces figures that
mislead rather than merely disappoint:

* **Field images share colour limits** across a whole figure. Autoscaling each panel makes
  a heavily smoothed field look identical to the reference.
* **No axes carries twenty series.** Where a ladder has many axes the figure facets by
  axis, with hue for the axis and lightness for the rung within it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fmeval.analysis import PROBE_LABELS, UNCORRELATED_LABEL

from .context import FigureItem, PlotResult
from .registry import plot
from .style import okabe, show_field, symmetric_limits


def _axis_frame(df: pd.DataFrame, axis: str) -> pd.DataFrame:
    return df[(df["degradation"] == axis) & (df["level"] > 0)]


def _median_by_level(df: pd.DataFrame, column: str = "value") -> pd.DataFrame:
    return (
        df.groupby(["level", "severity"], observed=True)[column]
        .agg(median="median", lo=lambda s: s.quantile(0.25),
             hi=lambda s: s.quantile(0.75))
        .reset_index()
        .sort_values("level")
    )


# --- section 3: does it see damage? ------------------------------------------------------


@plot(
    section=3, order=10, scope="per_metric_field",
    title="Response to each degradation",
    requires_columns=("degradation", "level", "value"),
    defaults={"logy": "auto", "band": True},
)
def ladder_curves(ctx, df, opts) -> PlotResult:
    """Metric value against rung, one line per ladder axis, with an interquartile band.

    The curve the rank correlation summarises. A flat line means the metric does not see
    that failure mode at all; a curve that jumps to its maximum at rung 1 has no resolving
    power in the regime that matters.
    """
    metric, field = str(df["metric"].iloc[0]), str(df["field"].iloc[0])
    axes_present = [a for a in ctx.ordinal_axes if a in set(df["degradation"])]
    ctx.require(bool(axes_present), "no ordinal ladder axes")

    fig, grid = ctx.style.figure(1, 1)
    ax = grid[0, 0]
    tidy = []
    for name in axes_present:
        stats = _median_by_level(_axis_frame(df, name))
        if stats.empty:
            continue
        colour = ctx.style.axis_colour(name)
        ax.plot(stats["level"], stats["median"], marker="o", ms=3.5,
                color=colour, ls=ctx.style.axis_style(name), label=ctx.label(name))
        if opts.get("band"):
            ax.fill_between(stats["level"], stats["lo"], stats["hi"],
                            color=colour, alpha=0.15, lw=0)
        stats.insert(0, "degradation", name)
        tidy.append(stats)

    anchor = df[df["degradation"] == UNCORRELATED_LABEL]
    if not anchor.empty:
        ax.axhline(float(anchor["value"].median()), color="0.4", ls=":", lw=1)
        ax.text(0.99, float(anchor["value"].median()), " unrelated fields",
                transform=ax.get_yaxis_transform(), va="bottom", ha="right",
                fontsize="x-small", color="0.4")

    ax.set_xlabel("rung (0 = reference)")
    ax.set_ylabel(f"{metric} [{_units(ctx, metric)}]")
    ax.set_title(f"{metric} on {field}")
    if _use_log(df["value"], opts.get("logy")):
        ax.set_yscale("log")
    ax.legend(fontsize="x-small", ncol=2)

    return PlotResult(
        [FigureItem(fig, {"metric": metric, "field": field},
                    caption=f"{metric} against rung for each ladder axis, on {field}. "
                            "Line is the median over frames, band the interquartile "
                            "range. The dotted line marks the value two statistically "
                            "identical but positionally unrelated fields receive.",
                    data=pd.concat(tidy, ignore_index=True) if tidy else None)]
    )


# --- section 4: is the response reliable? --------------------------------------------------


@plot(
    section=4, order=10, scope="per_field",
    title="Rank correlation per axis",
    requires_columns=("degradation", "level", "value"), min_axes=1,
)
def monotonicity_heatmap(ctx, df, opts) -> PlotResult:
    """Spearman correlation for every metric against every ladder axis.

    Read down a column for whether one metric is monotone; read across a row for the
    selectivity profile -- what that metric actually detects. Hatched cells fall below the
    configured reference value.
    """
    field = str(df["field"].iloc[0])
    rows = ctx.axes[(ctx.axes["field"] == field) & (~ctx.axes["is_probe"])]
    ctx.require(not rows.empty, f"no ordinal axes for {field}")
    grid_df = rows.pivot_table(index="metric", columns="degradation", values="rho",
                               observed=True)
    ctx.require(grid_df.size > 0, "empty correlation grid")

    fig, axgrid = ctx.style.figure(
        1, 1,
        w=max(3.5, 0.9 * grid_df.shape[1] + 1.6),
        h=max(2.0, 0.42 * len(grid_df) + 1.4),
    )
    ax = axgrid[0, 0]
    image = ax.imshow(grid_df.to_numpy(), cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(grid_df.shape[1]))
    ax.set_xticklabels([ctx.label(c) for c in grid_df.columns], rotation=40, ha="right")
    ax.set_yticks(range(len(grid_df)))
    ax.set_yticklabels(list(grid_df.index))
    ax.grid(False)

    limit = float(ctx.thresholds.get("spearman", np.nan))
    for i, metric in enumerate(grid_df.index):
        for j, axis in enumerate(grid_df.columns):
            value = grid_df.iloc[i, j]
            if not np.isfinite(value):
                continue
            ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize="xx-small",
                    color="white" if abs(value) > 0.6 else "black")
            if np.isfinite(limit) and value < limit:
                ax.add_patch(
                    __import__("matplotlib").patches.Rectangle(
                        (j - 0.5, i - 0.5), 1, 1, fill=False, hatch="///",
                        edgecolor="black", lw=1.2)
                )
    fig.colorbar(image, ax=ax, label="Spearman correlation", shrink=0.85)
    ax.set_title(f"Rank correlation with severity — {field}")

    return PlotResult(
        [FigureItem(fig, {"field": field},
                    caption=f"Spearman correlation between rung and metric value on "
                            f"{field}, computed within each ladder axis. Hatched cells "
                            f"fall below the reference value of {limit:g}.",
                    data=grid_df.reset_index())]
    )


# --- section 5: separability ---------------------------------------------------------------


@plot(
    section=5, order=10, scope="per_metric_field",
    title="Distribution of each rung over time",
    requires_columns=("degradation", "level", "value"), min_frames=4,
)
def rung_separation(ctx, df, opts) -> PlotResult:
    """Spread of each rung's values across frames, as violins grouped by axis.

    Where adjacent violins overlap, the metric cannot distinguish two models one rung
    apart however clean its median curve looks.
    """
    metric, field = str(df["metric"].iloc[0]), str(df["field"].iloc[0])
    axes_present = [a for a in ctx.ordinal_axes if a in set(df["degradation"])]
    ctx.require(bool(axes_present), "no ordinal ladder axes")

    # Wrap into a grid rather than one long row: a dozen panels side by side collapse to
    # zero width once axis decorations are accounted for.
    ncols = min(4, len(axes_present))
    nrows = int(np.ceil(len(axes_present) / ncols))
    fig, grid = ctx.style.figure(nrows, ncols, sharey=True)
    flat = [grid[r, c] for r in range(nrows) for c in range(ncols)]
    for ax in flat[len(axes_present):]:
        ax.set_axis_off()

    tidy = []
    for column, name in enumerate(axes_present):
        ax = flat[column]
        sub = _axis_frame(df, name)
        levels = sorted(sub["level"].unique())
        data = [sub.loc[sub["level"] == lv, "value"].to_numpy() for lv in levels]
        if not any(len(d) > 1 for d in data):
            ax.set_axis_off()
            continue
        parts = ax.violinplot(data, positions=levels, showextrema=False, widths=0.8)
        for body, colour in zip(parts["bodies"],
                                ctx.style.level_colours(ctx.style.axis_colour(name),
                                                        len(levels))):
            body.set_facecolor(colour)
            body.set_alpha(0.85)
        auc = ctx.axis_rows(metric=metric, field=field, degradation=name)
        if not auc.empty and np.isfinite(auc["separability_auc_min"].iloc[0]):
            ax.set_title(f"{ctx.label(name)}\nmin AUC {auc['separability_auc_min'].iloc[0]:.2f}",
                         fontsize="x-small")
        else:
            ax.set_title(ctx.label(name), fontsize="x-small")
        ax.set_xlabel("rung")
        for lv, values in zip(levels, data):
            tidy.append({"degradation": name, "level": lv,
                         "median": float(np.median(values)), "n": len(values)})
    for r in range(nrows):
        grid[r, 0].set_ylabel(metric)
    fig.suptitle(f"{metric} on {field}: rung distributions over frames", fontsize="small")

    return PlotResult(
        [FigureItem(fig, {"metric": metric, "field": field},
                    caption="Distribution of each rung's values across frames. Adjacent "
                            "violins that overlap cannot be told apart by this metric; "
                            "the annotated AUC is the smallest adjacent-rung separation.",
                    data=pd.DataFrame(tidy))]
    )


# --- section 6: when and where does it fire? --------------------------------------------------


@plot(
    section=6, order=10, scope="per_field",
    title="Reference field and its degraded variants",
    requires_maps=True,
    defaults={"cmap": "RdBu_r"},
)
def field_gallery(ctx, df, opts) -> PlotResult:
    """The reference field beside each degraded variant, on shared colour limits.

    Shared limits are not a stylistic choice: autoscaling each panel would make a heavily
    smoothed field look identical to the reference, which is the opposite of what the
    figure is for.
    """
    field = str(df["field"].iloc[0])
    stored = {k: v for k, v in ctx.maps.items() if f":{field}__" in k}
    ctx.require(bool(stored), f"no stored maps for {field}")

    reference = ctx.maps.get(f"__field__{field}")
    panels = sorted(stored)[:12]
    n = len(panels) + (1 if reference is not None else 0)
    ncols = min(4, n)
    nrows = int(np.ceil(n / ncols))
    fig, grid = ctx.style.figure(nrows, ncols)
    flat = [grid[r, c] for r in range(nrows) for c in range(ncols)]

    limits = symmetric_limits(np.concatenate([v.ravel() for v in stored.values()]), 0.995)
    i = 0
    if reference is not None:
        show_field(flat[0], reference, cmap=opts.get("cmap"), vmin=limits[0], vmax=limits[1])
        flat[0].set_title("reference", fontsize="x-small")
        i = 1
    for key in panels:
        ax = flat[i]
        show_field(ax, stored[key], cmap="magma")
        ax.set_title(key.split("__", 1)[1].rsplit("__", 1)[0], fontsize="xx-small")
        ax.set_xticks([]); ax.set_yticks([])
        i += 1
    for ax in flat[i:]:
        ax.set_axis_off()
    fig.suptitle(f"Pointwise metric density — {field}", fontsize="small")

    return PlotResult(
        [FigureItem(fig, {"field": field},
                    caption="Per-cell contribution to the metric for each stored variant. "
                            "A displaced feature shows as two lobes: one where it should "
                            "be and is not, one where it is and should not be.")]
    )


# --- section 7: what does it detect? --------------------------------------------------------


@plot(
    section=7, order=10, scope="per_field", min_metrics=2,
    title="Selectivity profile",
    requires_columns=("degradation", "level", "value"), min_axes=2,
)
def selectivity_profile(ctx, df, opts) -> PlotResult:
    """Each metric's response across every ladder axis, as grouped bars.

    Two metrics with near-identical profiles are redundant even when their magnitudes
    differ. A profile that is uniform across every axis indicates a metric responding to
    damage in general rather than to a specific failure mode.
    """
    field = str(df["field"].iloc[0])
    rows = ctx.axes[(ctx.axes["field"] == field) & (~ctx.axes["is_probe"])]
    ctx.require(rows["metric"].nunique() >= 2, "needs at least two metrics")
    grid_df = rows.pivot_table(index="degradation", columns="metric", values="rho",
                               observed=True)

    fig, axgrid = ctx.style.figure(1, 1)
    ax = axgrid[0, 0]
    positions = np.arange(len(grid_df))
    width = 0.8 / max(1, grid_df.shape[1])
    for i, metric in enumerate(grid_df.columns):
        ax.bar(positions + i * width, grid_df[metric].to_numpy(), width,
               label=metric, color=ctx.style.metric_colour(metric))
    ax.set_xticks(positions + 0.4 - width / 2)
    ax.set_xticklabels([ctx.label(a) for a in grid_df.index], rotation=40, ha="right")
    ax.set_ylabel("Spearman correlation")
    ax.set_title(f"What each metric detects — {field}")
    ax.legend(fontsize="x-small")

    return PlotResult(
        [FigureItem(fig, {"field": field},
                    caption="Rank correlation of each metric against each ladder axis.",
                    data=grid_df.reset_index())]
    )


# --- section 8: can it be fooled? ---------------------------------------------------------


@plot(
    section=8, order=10, scope="per_field",
    title="Response to deliberately misleading fields",
    requires_columns=("damage",),
    requires_degradations=("gaussian_impostor",),
)
def deception_panel(ctx, df, opts) -> PlotResult:
    """Damage assigned to the misleading fields, against the ordinary ladder.

    The spectrum-matched Gaussian field preserves the energy spectrum and the two-point
    correlation exactly while destroying all phase information, so a metric built only on
    second-order statistics scores it as perfect. The positionally unrelated field
    preserves every statistic while destroying alignment, so it defines a damage of 1.
    """
    field = str(df["field"].iloc[0])
    metrics = sorted(df["metric"].unique())
    ladder = df[(df["level"] > 0) & (~df["degradation"].isin(PROBE_LABELS))]

    fig, grid = ctx.style.figure(1, 1, h=max(2.0, 0.45 * len(metrics) + 1.2))
    ax = grid[0, 0]
    tidy = []
    for row, metric in enumerate(metrics):
        rungs = ladder[ladder["metric"] == metric]["damage"].dropna()
        if len(rungs):
            ax.plot(rungs, [row] * len(rungs), "o", mfc="none", mec="0.65", ms=4, zorder=2)
        impostor = df[(df["metric"] == metric)
                      & (df["degradation"] == "gaussian_impostor")]["damage"].median()
        ax.hlines(row, 0, impostor, color="0.85", lw=1, zorder=1)
        ax.plot(impostor, row, marker="*", ms=13, zorder=3, color=okabe("vermillion"),
                label="spectrum-matched Gaussian" if row == 0 else None)
        tidy.append({"metric": metric, "impostor_damage": float(impostor)})

    ax.axvline(1.0, color="0.3", lw=1)
    ax.text(1.0, -0.7, " unrelated fields", fontsize="x-small", color="0.3", va="top")
    limit = float(ctx.thresholds.get("impostor_damage", np.nan))
    if np.isfinite(limit):
        ax.axvline(limit, color="0.5", ls="--", lw=1)
    ax.set_yticks(range(len(metrics)))
    ax.set_yticklabels(metrics)
    ax.set_xlabel("damage (0 = clean, 1 = unrelated fields)")
    ax.set_title(f"Misleading fields — {field}")
    ax.legend(fontsize="x-small", loc="lower right")

    return PlotResult(
        [FigureItem(fig, {"field": field},
                    caption="Damage assigned to the spectrum-matched Gaussian field "
                            "(star) against the ordinary ladder rungs (open circles). "
                            "A metric that places the star near zero is responding only "
                            "to second-order statistics.",
                    data=pd.DataFrame(tidy))],
        notes=["A metric near the origin here sees only the energy spectrum."],
    )


# --- section 9: displacement ------------------------------------------------------------------


@plot(
    section=9, order=10, scope="per_field",
    title="Response to pure displacement",
    requires_columns=("damage",),
    defaults={"axes": ("translate_subpixel", "translate_x", "translate_y")},
)
def displacement_response(ctx, df, opts) -> PlotResult:
    """Damage against displacement distance, one line per metric.

    A pure translation leaves shape and amplitude exactly correct and changes only
    position, so this isolates position sensitivity from every other kind. A metric that
    reaches the unrelated-field level after a displacement much smaller than the structures
    in the field is exhibiting the double penalty.
    """
    field = str(df["field"].iloc[0])
    wanted = [a for a in opts.get("axes", ()) if a in set(df["degradation"])]
    ctx.require(bool(wanted), "no translation axis in the ladder")

    fig, grid = ctx.style.figure(1, 1)
    ax = grid[0, 0]
    tidy = []
    for metric in sorted(df["metric"].unique()):
        points = []
        for axis in wanted:
            sub = df[(df["metric"] == metric) & (df["degradation"] == axis)
                     & (df["level"] > 0)]
            stats = sub.groupby("severity", observed=True)["damage"].median()
            points.extend(zip(stats.index, stats.to_numpy()))
        if not points:
            continue
        points.sort()
        distance = [p[0] for p in points]
        damage = [p[1] for p in points]
        ax.plot(distance, damage, marker="o", ms=3.5,
                color=ctx.style.metric_colour(metric), label=metric)
        tidy.extend({"metric": metric, "distance": d, "damage": v}
                    for d, v in points)

    # Declared before the log scale is set, not after. A metric with no dynamic range has an
    # all-NaN damage column -- which AGENTS.md section 3 explicitly calls correct for a
    # single-field invariant rather than a bug -- and matplotlib then raises "Data cannot be
    # log-scaled because all values are <= 0" from inside the renderer. The contract is that
    # unavailability is declared with ctx.require, so this is a skip, not an error. issues/039.
    ctx.require(
        any(np.isfinite(row["damage"]) for row in tidy),
        "no finite damage on the displacement axis: the metric has no dynamic range between "
        "clean and the unrelated-field anchor, so there is nothing to plot against distance",
    )

    ax.axhline(1.0, color="0.3", lw=1)
    ax.text(0.01, 1.0, "unrelated fields", fontsize="x-small", color="0.3",
            va="bottom", transform=ax.get_yaxis_transform())
    ax.set_xscale("log")
    ax.set_xlabel("displacement [cells]")
    ax.set_ylabel("damage")
    ax.set_title(f"Pure displacement — {field}")
    ax.legend(fontsize="x-small")

    return PlotResult(
        [FigureItem(fig, {"field": field},
                    caption="Damage against displacement distance. Shape and amplitude "
                            "are exactly correct at every point on this curve; only "
                            "position changes.",
                    data=pd.DataFrame(tidy))]
    )


# --- section 10: cost -----------------------------------------------------------------------


@plot(
    section=10, order=10, scope="global", min_metrics=2,
    title="Cost against worst-axis correlation",
    requires_columns=("wall_time_s",),
)
def cost_frontier(ctx, df, opts) -> PlotResult:
    """Worst-axis rank correlation against wall-clock cost, one point per metric.

    Upper left is the useful region. A metric in the upper right gives the right answer at
    a price that may rule it out as a training loss while leaving it usable as a
    diagnostic.
    """
    card = ctx.card
    ctx.require("rho_min" in card.columns and len(card) >= 2, "needs at least two metrics")
    fig, grid = ctx.style.figure(1, 1)
    ax = grid[0, 0]
    for _, row in card.iterrows():
        ax.scatter(row["cost_s"], row["rho_min"], s=45,
                   color=ctx.style.metric_colour(row["metric"]), zorder=3)
        ax.annotate(f"{row['metric']} ({row['field']})",
                    (row["cost_s"], row["rho_min"]),
                    textcoords="offset points", xytext=(6, 3), fontsize="xx-small")
    ax.set_xscale("log")
    ax.set_xlabel("wall clock per evaluation [s]")
    ax.set_ylabel("worst-axis Spearman correlation")
    ax.set_title("Cost against reliability")
    return PlotResult([FigureItem(fig, {}, caption="Each point is one metric and field.",
                                  data=card[["metric", "field", "cost_s", "rho_min"]])])


# --- helpers -------------------------------------------------------------------------------


def _units(ctx, metric: str) -> str:
    snapshot = ctx.meta.get("registries", {}).get("metrics", {})
    return snapshot.get(metric, {}).get("units", "")


def _use_log(values: pd.Series, setting) -> bool:
    if setting is not True and setting != "auto":
        return False
    positive = values[values > 0]
    if len(positive) < 3:
        return False
    return bool(positive.max() / positive.min() > 100)


@plot(
    section=3, order=5, scope="per_field",
    title="Where the field keeps its energy",
    requires_columns=("field", "severity", "calibration"),
)
def energy_spectrum(ctx, df, opts) -> PlotResult:
    """Cumulative fluctuation energy against wavenumber, with the applied cutoffs marked.

    This is the figure that explains the resolution of every filter ladder in the report. A
    severity on a spectral axis is a fraction of energy to remove, and the harness converts it to
    a cutoff using exactly this curve -- so where the curve is steep, neighbouring rungs land on
    the same wavenumber shell and cannot be separated, and where it is shallow they spread out.

    Read the steepness first. Measured on this data the density curve is almost a step: 3e-5 of its
    fluctuation energy lies at or below |k| = 1 and 69% at |k| = sqrt(2), so two consecutive
    available cutoffs differ by most of the field and a sharp filter has only a couple of usable
    rungs there however the ladder is configured. Vorticity rises gradually -- 50% by |k| = 3.2,
    90% by 23, 99% by 51 -- and its cutoffs spread over more than a factor of ten as a result.
    """
    ctx.require(not ctx.spectrum.empty,
                "no measured spectrum in this run (it predates severity calibration)")
    field = str(df["field"].iloc[0])
    curve = ctx.spectrum[ctx.spectrum["field"] == field].sort_values("wavenumber")
    ctx.require(not curve.empty, f"no measured spectrum for {field}")

    cuts = df[df["calibration"].astype(str).str.startswith("energy") & (df["level"] > 0)]

    fig, axgrid = ctx.style.figure(1, 1)
    ax = axgrid[0, 0]
    k = curve["wavenumber"].to_numpy()
    cumulative = curve["cumulative_energy_below"].to_numpy()
    ax.plot(k, cumulative, marker="o", markersize=2.5, lw=1.4, color="black",
            label="cumulative energy below $k$")
    ax.set_xscale("symlog", linthresh=1)
    ax.set_xlim(0, max(k.max(), 2))
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("wavenumber $k$")
    ax.set_ylabel("fraction of fluctuation energy below $k$")

    # The applied cutoffs, so a reader can see which rungs share a shell.
    rows = []
    for axis, g in cuts.groupby("degradation", observed=True):
        colour = ctx.style.axis_colour(str(axis))
        for level, h in g.groupby("level", observed=True):
            cutoff = float(h["severity"].iloc[0])
            removed = float(h["energy_removed"].median())
            degenerate = bool(h["severity_degenerate"].iloc[0])
            ax.axvline(cutoff, color=colour, lw=1.0,
                       ls=":" if degenerate else "--", alpha=0.85)
            rows.append({"axis": str(axis), "level": int(level), "cutoff": cutoff,
                         "energy_removed": removed, "excluded": degenerate})
        ax.plot([], [], color=colour, ls="--", label=f"{ctx.label(str(axis))} cutoffs")

    ax.legend(fontsize="xx-small", loc="lower right")
    ax.set_title(f"Fluctuation energy distribution — {field}")

    note = (
        "Dashed lines are the cutoffs the configured severities resolved to; dotted lines are "
        "rungs excluded because they landed on the same shell as a milder rung or on a no-op."
    )
    return PlotResult(
        figures=[FigureItem(
            fig=fig, keys={"field": field},
            caption=f"Cumulative fluctuation energy for {field}, with the applied spectral "
                    "cutoffs. The steeper the curve, the fewer distinct rungs a sharp filter "
                    "can produce.",
            data=pd.concat([curve.assign(kind="spectrum"),
                            pd.DataFrame(rows).assign(kind="cutoff")], ignore_index=True),
        )],
        notes=[note],
    )
