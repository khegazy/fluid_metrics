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
from .prose import FAMILY_HEADINGS

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


def _cell(row: Any, column: str) -> Any:
    """A probe column that may be absent from this run's analysis.

    `probe_summary` only emits columns for the probes the ladder actually ran. A run whose
    ladder skipped the impostor -- `degradation.skip=[gaussian_impostor]`, or a custom
    ladder -- legitimately lacks those columns, and indexing them raised a bare KeyError
    that named a column instead of the situation. Absent means not measured, which
    `_fmt` renders as an em dash.
    """
    return row[column] if column in row.index else None


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

    lines = ["| test family | field | degradations | rank correlation | weakest gap "
             "between neighbouring strengths | first strength detected |",
             "|---|---|---|---|---|---|"]
    for family, group in axes[~axes["is_probe"]].groupby("degradation_family"):
        # The same readable name the matching '### ' subsection uses, so a reader moving
        # between the summary and the detail is not asked to learn two vocabularies.
        named = FAMILY_HEADINGS.get(family, family)
        for field, sub in group.groupby("field"):
            lines.append(
                f"| {named} | {field} | {len(sub)} | "
                f"{_fmt(sub['rho'].min())} to {_fmt(sub['rho'].max())} | "
                f"{_fmt(sub['separability_auc_min'].min())} | "
                f"level {_fmt(sub['sensitivity_level'].min())} |"
            )
    probes = run.probes[run.probes["metric"] == metric]
    for _, row in probes.iterrows():
        lines.append(
            f"| trap test: fake prediction, right spectrum | {row['field']} | 1 | — | — | "
            f"damage {_fmt(_cell(row, 'gaussian_impostor_damage'))} |"
        )
    lines += [
        "",
        "One row per family of degradation and physical field. **Rank correlation** asks "
        "whether the metric put the strengths of one degradation in the right order: it "
        "is the Spearman correlation between the metric and the applied strength, "
        "computed inside a single frame, and the column gives the range over the "
        "degradations in that family. A value of 1 means every strength was ordered "
        "correctly in every frame. **Weakest gap between neighbouring strengths** asks "
        "whether the metric can tell one strength from the next: it is the smallest "
        "Mann-Whitney overlap between any two neighbouring strengths, where 1 means the "
        "two never overlap and 0.5 means the metric cannot separate them at all. "
        "**First strength detected** is the mildest strength at which the metric has "
        "moved a tenth of the way from the undegraded reference toward a field with no "
        "relation to the truth; a dash means the metric never reached that tenth. "
        "**Damage** is that same 0-to-1 scale read as a number: 0 is the undegraded "
        "reference and 1 is an unrelated field.",
        "",
        "This table reports what was measured and grades none of the measurements. What "
        "the numbers mean for this metric is written in the subsections below, beside the "
        "test that produced each number.",
    ]
    return "\n".join(lines)


def family_block(run: Run, metric: str, family: str) -> str:
    """One family's numbers, one row per degradation and physical field."""
    axes = run.axes[(run.axes["metric"] == metric)
                    & (run.axes["degradation_family"] == family)
                    & (~run.axes["is_probe"])]
    if axes.empty:
        return NOT_MEASURED
    lines = ["| degradation | field | strengths | rank correlation | "
             "fraction of frames in the right order | weakest gap between neighbouring "
             "strengths |",
             "|---|---|---|---|---|---|"]
    for _, row in axes.sort_values(["degradation", "field"]).iterrows():
        lines.append(
            f"| `{row['degradation']}` | {row['field']} | {int(row['n_levels'])} | "
            f"{_fmt(row['rho'])} | {_fmt(row['monotone_fraction'])} | "
            f"{_fmt(row['separability_auc_min'])} |"
        )
    return "\n".join(lines)


def canaries_block(run: Run, metric: str) -> str:
    """What the metric assigns to the fake prediction and to an unrelated field."""
    probes = run.probes[run.probes["metric"] == metric]
    if probes.empty:
        return NOT_MEASURED
    lines = ["| field | damage assigned to the fake prediction | closest real degradation "
             "| value on an unrelated field |",
             "|---|---|---|---|"]
    for _, row in probes.sort_values("field").iterrows():
        nearest = _cell(row, "gaussian_impostor_nearest_level")
        lines.append(
            f"| {row['field']} | {_fmt(_cell(row, 'gaussian_impostor_damage'))} | "
            f"{'`' + str(nearest) + '`' if nearest is not None else '—'} | "
            f"{_fmt(_cell(row, 'uncorrelated_value'))} |"
        )
    lines += [
        "",
        "The fake prediction here has exactly the reference field's amplitude spectrum "
        "and completely scrambled structure. Damage of 1 is what a field with no relation "
        "to the truth scores, so the damage column says how close to useless this metric "
        "considers that fake prediction: a low number means the metric was fooled. The "
        "third column translates the same number into an ordinary degradation whose "
        "damage the fake prediction matches, which is easier to picture.",
    ]
    return "\n".join(lines)


def summary_block(run: Run, metric: str) -> str:
    """What holds across every degradation: how this metric relates to the others.

    ``cross_metric_correlation`` returns a square matrix indexed by metric, so the row
    for this metric is read and the self-correlation dropped.
    """
    matrix = an.cross_metric_correlation(run.rows)
    if matrix.empty or metric not in matrix.columns:
        return NOT_MEASURED

    row = matrix.loc[metric].drop(labels=[metric], errors="ignore").sort_values(ascending=False)
    lines = ["| compared with | rank correlation over every degradation |", "|---|---|"]
    for other, value in row.items():
        lines.append(f"| `{other}` | {_fmt(float(value))} |")
    lines += [
        "",
        "Computed on the median value at each combination of degradation and strength, "
        "over every degradation and physical field in the run, with the undegraded "
        "reference excluded. Two metrics correlating near 1 put the degradations in the "
        "same order, but the two may still weight those degradations very differently. "
        "A correlation near 1 therefore means the two metrics are redundant for ranking "
        "models, not that the two are interchangeable as training losses.",
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
    from .exemplars import sanitize_json

    out.write_text(
        json.dumps(sanitize_json(fingerprint), indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    )
    for stale in bundle.path.glob("_generated/results_*.md"):
        stale.unlink()
    for stale in (bundle.path / "_generated" / "performance.md",
                  bundle.path / "_generated" / "run.md"):
        stale.unlink(missing_ok=True)
    return out
