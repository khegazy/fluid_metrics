"""Turn one evaluation run into the measured half of every metric card.

Consumes a run folder rather than running the pipeline itself. The evaluation is
expensive and happens where the data lives; generating documentation from its output is
cheap and should not require repeating it. That separation also means a card's numbers
can always be traced to a named run rather than to whenever someone last regenerated.

Nothing here computes a statistic of its own. Every number comes from
:mod:`fmeval.analysis`, which is the same code the LaTeX report uses, so a card and a
report of the same run cannot disagree.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from fmeval import analysis as an

from .exemplars import load_cards_config, write_block

#: Which generated block each degradation family's results go into.
FAMILY_BLOCKS = {
    "smoothing": "results_smoothing",
    "spectral": "results_spectral",
    "geometric": "results_geometric",
    "resolution": "results_resolution",
    "stochastic": "results_stochastic",
    "pointwise": "results_pointwise",
}

NOT_MEASURED = "No measurements for this test in the recorded run."


@dataclass(frozen=True)
class Run:
    """One evaluation run, with the statistics derived from it."""

    folder: Path
    rows: pd.DataFrame
    meta: dict
    axes: pd.DataFrame
    probes: pd.DataFrame
    norm: pd.DataFrame


def load_run(folder: Path) -> Run:
    """Read a run folder and derive every statistic a card reports.

    Args:
        folder: A ``results/<name>_<stamp>`` directory containing ``data/results.csv``.

    Returns:
        The run and its analysis.

    Raises:
        FileNotFoundError: If the folder holds no results.
        ValueError: If the run is on a dataset cards may not cite -- the dev dataset is
            the first 100 solver steps, before the flow develops, and its numbers would be
            indistinguishable once written into a card from ones that mean something.
    """
    results = folder / "data" / "results.csv"
    if not results.is_file():
        results = folder / "data" / "results.csv.gz"
    if not results.is_file():
        raise FileNotFoundError(f"{folder} has no data/results.csv")

    rows = pd.read_csv(results)
    allowed = list(load_cards_config().evidence_datasets)
    used = sorted(rows["dataset"].unique())
    forbidden = [d for d in used if d not in allowed]
    if forbidden:
        raise ValueError(
            f"{folder} is on {forbidden}, which cards may not cite; allowed: {allowed}.\n"
            "Evidence must come from a developed-flow run, not a smoke test."
        )

    meta_path = folder / "data" / "run_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
    norm = an.normalisation(rows)
    return Run(folder=folder, rows=rows, meta=meta, norm=norm,
               axes=an.summarise_axes(rows, norm=norm),
               probes=an.probe_summary(rows, norm))


def _fmt(value: Any, digits: int = 3) -> str:
    """A number for a table cell, or an em dash where there is none."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


def run_block(run: Run) -> str:
    """The provenance every number below it inherits."""
    meta, rows = run.meta, run.rows
    frames = sorted(rows["frame_index"].unique())
    git = meta.get("git", {})
    sha = str(git.get("sha") or git.get("commit") or "not recorded")[:12]
    dirty = " (working tree dirty)" if git.get("dirty") else ""
    return (
        f"Measured on `{rows['dataset'].iloc[0]}`, frames {frames[0]} to {frames[-1]} "
        f"({len(frames)} frames of developed flow), on the "
        f"{meta.get('analysis_grid') or 'native'} analysis grid, seed "
        f"{meta.get('seed', '—')}, at commit `{sha}`{dirty}. Run `{run.folder.name}`.\n\n"
        f"Every number in this section comes from that one run. Regenerate with "
        f"`python -m fmeval.cards evidence <name> --results {run.folder}`."
    )


def performance_block(run: Run, metric: str) -> str:
    """The summary table: how this metric behaved on every test, at a glance."""
    axes = run.axes[run.axes["metric"] == metric]
    if axes.empty:
        return NOT_MEASURED

    lines = ["| test | field | axes | rank correlation | weakest separation | first detected |",
             "|---|---|---|---|---|---|"]
    for family, group in axes[~axes["is_probe"]].groupby("degradation_family"):
        for field, sub in group.groupby("field"):
            lines.append(
                f"| {family} | {field} | {len(sub)} | "
                f"{_fmt(sub['rho'].min())} to {_fmt(sub['rho'].max())} | "
                f"{_fmt(sub['separability_auc_min'].min())} | "
                f"level {_fmt(sub['sensitivity_level'].min())} |"
            )
    probes = run.probes[run.probes["metric"] == metric]
    for _, row in probes.iterrows():
        lines.append(
            f"| canary: phase-randomised impostor | {row['field']} | 1 | — | — | "
            f"damage {_fmt(row['gaussian_impostor_damage'])} |"
        )
    lines += [
        "",
        "Rank correlation is the per-frame Spearman correlation of the metric with "
        "severity, reported as the range over the axes in that family; 1 means every "
        "severity ordered correctly in every frame. Weakest separation is the smallest "
        "Mann-Whitney overlap between neighbouring severities. First detected is the "
        "lowest severity level at which the metric departs from clean by a tenth of the "
        "distance to an unrelated field. Damage is on that same scale: 0 is the reference "
        "and 1 is an unrelated field.",
        "",
        "This table reports what was measured and grades none of it. What the numbers mean "
        "for this metric is in the subsections below, beside the test that produced each.",
    ]
    return "\n".join(lines)


def family_block(run: Run, metric: str, family: str) -> str:
    """One family's per-axis numbers, for every field."""
    axes = run.axes[(run.axes["metric"] == metric)
                    & (run.axes["degradation_family"] == family)
                    & (~run.axes["is_probe"])]
    if axes.empty:
        return NOT_MEASURED
    lines = ["| axis | field | levels | rank correlation | monotone frames | weakest separation |",
             "|---|---|---|---|---|---|"]
    for _, row in axes.sort_values(["degradation", "field"]).iterrows():
        lines.append(
            f"| `{row['degradation']}` | {row['field']} | {int(row['n_levels'])} | "
            f"{_fmt(row['rho'])} | {_fmt(row['monotone_fraction'])} | "
            f"{_fmt(row['separability_auc_min'])} |"
        )
    return "\n".join(lines)


def canaries_block(run: Run, metric: str) -> str:
    """What the metric assigns to the impostor and to an unrelated field."""
    probes = run.probes[run.probes["metric"] == metric]
    if probes.empty:
        return NOT_MEASURED
    lines = ["| field | impostor damage | nearest severity level | unrelated-field value |",
             "|---|---|---|---|"]
    for _, row in probes.sort_values("field").iterrows():
        lines.append(
            f"| {row['field']} | {_fmt(row['gaussian_impostor_damage'])} | "
            f"`{row['gaussian_impostor_nearest_level']}` | "
            f"{_fmt(row['uncorrelated_value'])} |"
        )
    lines += [
        "",
        "Damage of 1 is what an unrelated field scores, so the impostor column says how "
        "close to useless this metric considers a field with the reference's spectrum and "
        "random phases. The nearest severity level names the ordinary degradation whose "
        "damage the impostor most resembles, which is the more legible statement of the "
        "same thing.",
    ]
    return "\n".join(lines)


def summary_block(run: Run, metric: str) -> str:
    """What holds across every axis: how this metric relates to the others.

    ``cross_metric_correlation`` returns a square matrix indexed by metric, so the row
    for this metric is read and the self-correlation dropped.
    """
    matrix = an.cross_metric_correlation(run.rows)
    if matrix.empty or metric not in matrix.columns:
        return NOT_MEASURED

    row = matrix.loc[metric].drop(labels=[metric], errors="ignore").sort_values(ascending=False)
    lines = ["| against | rank correlation across the ladder |", "|---|---|"]
    for other, value in row.items():
        lines.append(f"| `{other}` | {_fmt(float(value))} |")
    lines += [
        "",
        "Computed on the median value at each (axis, severity level), over every axis and "
        "field in the run, with the reference excluded. Two metrics correlating near 1 "
        "order the degradations alike; they may still weight them very differently, so "
        "this says they are redundant for ranking models rather than interchangeable as "
        "training losses.",
    ]
    return "\n".join(lines)


def generate(metric: str, run: Run) -> Path:
    """Write every generated block of one metric's card, and its fingerprint.

    Args:
        metric: The metric bundle to fill in.
        run: The run to take every number from.

    Returns:
        The path to the written fingerprint.

    Raises:
        KeyError: If the bundle does not exist, or its card lacks a block the generator
            writes -- which means the card and the generator disagree about what is
            generated.
    """
    from .loader import find_bundle

    bundle = find_bundle(metric)
    if bundle is None:
        raise KeyError(f"no metric bundle named {metric!r}")

    command = f"python -m fmeval.cards evidence {metric} --results {run.folder}"
    blocks = {
        "run": run_block(run),
        "performance": performance_block(run, metric),
        "results_canaries": canaries_block(run, metric),
        "results_summary": summary_block(run, metric),
    }
    for family, block in FAMILY_BLOCKS.items():
        blocks[block] = family_block(run, metric, family)

    text = bundle.card_md.read_text()
    for name, body in blocks.items():
        if f"<!-- GENERATED {name}:" in text:
            write_block(bundle.card_md, name, body, command=command)

    axes = run.axes[run.axes["metric"] == metric]
    probes = run.probes[run.probes["metric"] == metric]
    fingerprint = {
        "metric": metric,
        "dataset": str(run.rows["dataset"].iloc[0]),
        "run": run.folder.name,
        "frames": sorted(int(f) for f in run.rows["frame_index"].unique()),
        "seed": run.meta.get("seed"),
        "analysis_grid": run.meta.get("analysis_grid"),
        "git": run.meta.get("git", {}),
        "axes": json.loads(axes.to_json(orient="records")),
        "probes": json.loads(probes.to_json(orient="records")),
    }
    out = bundle.path / "_generated" / "fingerprint.json"
    out.write_text(json.dumps(fingerprint, indent=2, sort_keys=True) + "\n")
    for stale in bundle.path.glob("_generated/results_*.md"):
        stale.unlink()
    for stale in (bundle.path / "_generated" / "performance.md",
                  bundle.path / "_generated" / "run.md"):
        stale.unlink(missing_ok=True)
    return out
