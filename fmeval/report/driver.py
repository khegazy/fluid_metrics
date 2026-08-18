"""Run every renderer and assemble the LaTeX document.

The driver owns everything the renderers deliberately do not: precondition checks, paths,
file formats, rcParams, and the manifest. A renderer that cannot run is logged and
recorded, never fatal -- a failing figure must not destroy an expensive evaluation's
output.

Section prose is generated rather than boilerplate: each chapter quotes the measured
numbers inline and points at its figures, so the document reads as an assessment rather
than a folder of plots.
"""

from __future__ import annotations

import json
import logging
import time
import traceback
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field as dc_field
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import rc_context

from fmeval import analysis as an
from fmeval.io import RunFolder

from . import plots as _plots  # noqa: F401  (registers the figure renderers)
from . import tables as _tables  # noqa: F401  (registers the table renderers)
from .context import ReportContext
from .latex import booktabs_table, document, escape, figure, preamble, slug, verbatim
from .registry import (
    SECTIONS,
    RendererSpec,
    RendererUnavailable,
    check_preconditions,
    iter_renderers,
    iter_scope,
)
from .style import Style

log = logging.getLogger(__name__)


@dataclass
class Rendered:
    """Outcome of one renderer, for the manifest and for the document."""

    name: str
    kind: str
    section: int
    title: str
    status: str
    reason: str = ""
    files: list[str] = dc_field(default_factory=list)
    latex: list[str] = dc_field(default_factory=list)
    notes: list[str] = dc_field(default_factory=list)
    duration_s: float = 0.0


def _read_csv(path) -> pd.DataFrame:
    """Read an optional analysis CSV, empty if the run does not have it.

    Older run folders lack the newer files, and re-rendering one must not fail because of it.
    """
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def build_context(
    folder: RunFolder,
    *,
    theme: str = "notebook",
    thresholds: Mapping[str, float] | None = None,
    bootstrap: int = 200,
    block_length: int = 10,
) -> ReportContext:
    """Load a run folder and compute everything the renderers need.

    All the statistics happen here, once, so a figure and its table cannot disagree.
    """
    from fmeval.io import read_results

    df = read_results(folder)
    meta = _read_json(folder.data / "run_meta.json")
    config = _read_yaml(folder.data / "config.yaml")
    maps = _read_maps(folder.data / "error_maps.npz")
    spectrum = _read_csv(folder.data / "calibration_spectrum.csv")

    norm = an.normalisation(df)
    scored = an.add_damage(df, norm)
    axes = an.summarise_axes(scored, norm=norm, block_length=block_length,
                             n_bootstrap=bootstrap)
    probes = an.probe_summary(df, norm)
    card = an.flag(an.report_card(axes, probes, norm), thresholds or {})

    return ReportContext(
        df=scored,
        norm=norm,
        axes=axes,
        probes=probes,
        card=card,
        spectrum=spectrum,
        maps=maps,
        meta=meta,
        config=config,
        style=Style.build(theme, metrics=df["metric"].unique(),
                          axes=df["degradation"].unique()),
        thresholds=thresholds or {},
    )


def render(
    folder: RunFolder,
    ctx: ReportContext,
    *,
    only: Sequence[str] = (),
    skip: Sequence[str] = (),
    formats: Sequence[str] = ("pdf", "png"),
) -> list[Rendered]:
    """Run every registered renderer whose preconditions are met."""
    folder.create()
    results: list[Rendered] = []

    for spec in iter_renderers():
        if only and spec.name not in only:
            results.append(Rendered(spec.name, spec.kind, spec.section, spec.title,
                                    "disabled", "not selected"))
            continue
        if spec.name in skip or "*" in skip:
            results.append(Rendered(spec.name, spec.kind, spec.section, spec.title,
                                    "disabled", "skipped by config"))
            continue

        ok, why = check_preconditions(spec, ctx)
        if not ok:
            log.info("skip %s: %s", spec.name, why)
            results.append(Rendered(spec.name, spec.kind, spec.section, spec.title,
                                    "skipped", why))
            continue

        outcome = Rendered(spec.name, spec.kind, spec.section, spec.title, "ok")
        started = time.perf_counter()
        try:
            for keys, subset in iter_scope(spec.scope, ctx.df):
                opts = dict(spec.defaults)
                with rc_context(ctx.style.rc):
                    result = spec.fn(ctx, subset, opts)
                if spec.kind == "plot":
                    _emit_plot(folder, spec, result, formats, outcome)
                else:
                    _emit_table(folder, spec, result, outcome)
                outcome.notes.extend(getattr(result, "notes", []))
        except RendererUnavailable as exc:
            outcome.status, outcome.reason = "skipped", str(exc)
            log.info("skip %s: %s", spec.name, exc)
        except Exception:  # noqa: BLE001 - a bad figure must not lose the evaluation
            outcome.status = "error"
            outcome.reason = traceback.format_exc(limit=3)
            log.exception("renderer %s failed", spec.name)
        finally:
            plt.close("all")
            outcome.duration_s = time.perf_counter() - started
        results.append(outcome)

    return results


def _emit_plot(folder, spec, result, formats, outcome) -> None:
    for item in result.figures:
        stem = slug(spec.name, **item.keys)
        for suffix in formats:
            path = folder.plots / f"{stem}.{suffix}"
            item.fig.savefig(path)
            outcome.files.append(str(path.relative_to(folder.root)))
        if item.data is not None and not item.data.empty:
            item.data.to_csv(folder.figure_data / f"{stem}.csv", index=False)
        outcome.latex.append(
            figure(stem, caption=item.caption or spec.title, label=stem)
        )


def _emit_table(folder, spec, result, outcome) -> None:
    stem = slug(spec.name, **result.keys)
    csv_path = folder.data / f"{stem}.csv"
    result.frame.to_csv(csv_path, index=False)
    tex = booktabs_table(
        result.frame,
        caption=result.caption or spec.title,
        label=stem,
        formats=result.formats,
        headers=result.headers,
        note=result.note,
        landscape=result.landscape or result.frame.shape[1] > 8,
    )
    (folder.tables / f"{stem}.tex").write_text(tex)
    outcome.files.extend([
        str(csv_path.relative_to(folder.root)),
        f"tables/{stem}.tex",
    ])
    outcome.latex.append(f"\\input{{tables/{stem}}}\n")


# --- document assembly -------------------------------------------------------------------


def write_document(folder: RunFolder, ctx: ReportContext,
                   rendered: Sequence[Rendered]) -> Path:
    """Write ``preamble.tex``, ``sections/*.tex`` and ``main.tex``."""
    by_section: dict[int, list[Rendered]] = {}
    for item in rendered:
        by_section.setdefault(item.section, []).append(item)

    metric = ctx.meta.get("metric") or ", ".join(ctx.metrics)
    dataset = ctx.meta.get("dataset", "")
    (folder.root / "preamble.tex").write_text(
        preamble(f"Metric report: {metric}", f"dataset: {dataset}")
    )

    written: list[str] = []
    for section in SECTIONS:
        items = [i for i in by_section.get(section.number, []) if i.status == "ok"]
        prose = _section_prose(section.key, ctx)
        if not items and not prose:
            continue
        body = [f"\\section{{{escape(section.title)}}}", ""]
        if section.intro:
            body += [escape(section.intro), ""]
        if prose:
            body += [prose, ""]
        for item in sorted(items, key=lambda i: i.name):
            body.extend(item.latex)
        name = f"{section.number:02d}_{section.key}"
        (folder.sections / f"{name}.tex").write_text("\n".join(body) + "\n")
        written.append(name)

    (folder.root / "main.tex").write_text(
        document(written, title=f"Metric report: {metric}", subtitle=f"dataset: {dataset}")
    )
    return folder.root / "main.tex"


def _section_prose(key: str, ctx: ReportContext) -> str:
    """Generated commentary quoting the measured numbers, per section."""
    card = ctx.card
    if key == "overview":
        meta = ctx.meta
        snapshot = meta.get("registries", {}).get("metrics", {})
        metric = meta.get("metric", "")
        entry = snapshot.get(metric, {})
        lines = []
        if entry.get("doc"):
            lines.append(escape(entry["doc"]))
        lines.append(
            f"Evaluated on {escape(meta.get('dataset', 'the dataset'))} over "
            f"{meta.get('n_frames', '?')} frames and "
            f"{len(meta.get('ladder_axes', []) or [])} ladder axes, on an analysis grid of "
            f"{meta.get('analysis_grid', '?')}. Configuration hash "
            f"\\texttt{{{escape(meta.get('config_hash', ''))}}}."
        )
        if entry:
            lines.append(
                f"Arity {escape(entry.get('arity', ''))}; units "
                f"{escape(entry.get('units', ''))}; "
                + ("differentiable" if entry.get("differentiable") else
                   "not differentiable")
                + ", so it "
                + ("could" if entry.get("differentiable") else "could not")
                + " serve as a training loss."
            )
        return "\n\n".join(lines)

    if key == "headline" and not card.empty:
        parts = []
        for _, row in card.iterrows():
            bits = [f"On {escape(str(row['field']))}, the weakest axis is "
                    f"\\texttt{{{escape(str(row.get('worst_axis', '')))}}} with a rank "
                    f"correlation of {_fmt(row.get('rho_min'))}"]
            if np.isfinite(row.get("gaussian_impostor_damage", np.nan)):
                bits.append(
                    "the spectrum-matched Gaussian field is assigned a damage of "
                    f"{_fmt(row['gaussian_impostor_damage'])}, where 1 is the value two "
                    "unrelated fields receive"
                )
            flags = str(row.get("flags", ""))
            bits.append(
                f"flagged: {escape(flags)}" if flags else
                "no configured reference value was missed"
            )
            parts.append("; ".join(bits) + ".")
        return "\n\n".join(parts)

    if key == "reliability" and not ctx.axes.empty:
        ordinal = ctx.axes[~ctx.axes["is_probe"]]
        ordinal = ordinal[ordinal["rho"].notna()]
        if ordinal.empty:
            # Every ordinal axis has an undefined correlation. That is what a metric invariant
            # to the whole ladder produces, and it is a documented-correct configuration rather
            # than an error, so the section says so instead of taking down the report.
            return (
                "Rank correlation is undefined on every ladder axis: the metric's value does "
                "not vary across the severity levels by more than floating-point round-off. For a "
                "single-field invariant measured against operators that preserve it, that is "
                "the correct result rather than a defect."
            )
        best = ordinal.loc[ordinal["rho"].idxmax()]
        worst = ordinal.loc[ordinal["rho"].idxmin()]
        return (
            f"Rank correlation ranges from {_fmt(worst['rho'])} on "
            f"\\texttt{{{escape(worst['degradation'])}}} to {_fmt(best['rho'])} on "
            f"\\texttt{{{escape(best['degradation'])}}}. Each is computed within a single "
            "ladder axis; correlating across axes would be meaningless, since severities "
            "on different axes have no order relative to one another. Each is also "
            "computed within a single frame and then aggregated: pooling every frame "
            "together would conflate the response to severity with the evolution of the "
            "field along the trajectory, which on this data spans several orders of "
            "magnitude."
        )

    if key == "displacement":
        return (
            "A translation leaves every statistic of the field unchanged and alters only "
            "position. A metric that approaches the unrelated-field level after a "
            "displacement much smaller than the structures in the flow is exhibiting the "
            "double penalty: it is reporting a large error for a field that is correct in "
            "shape and amplitude."
        )

    if key == "robustness":
        return (
            "Two constructions are used. The spectrum-matched Gaussian field retains every "
            "Fourier amplitude and replaces every phase, so its energy spectrum and "
            "two-point correlation are identical to the reference to machine precision "
            "while its flatness collapses to the Gaussian value of three. A metric built "
            "only on second-order statistics cannot distinguish it from the reference. "
            "The positionally unrelated field is the reference translated by a large "
            "random offset, which preserves every statistic exactly while removing "
            "alignment, and therefore defines a damage of one."
        )

    if key == "reproducibility":
        config = _dump_yaml(ctx.config)
        command = ctx.meta.get("command", "")
        body = []
        if command:
            body.append(verbatim(command, caption="Command"))
        body.append(verbatim(config, caption="Resolved configuration"))
        return "\n".join(body)

    return ""


def write_manifest(folder: RunFolder, rendered: Sequence[Rendered]) -> Path:
    """Record every renderer's outcome, including why anything was skipped."""
    path = folder.data / "manifest.json"
    path.write_text(json.dumps([asdict(r) for r in rendered], indent=2) + "\n")
    return path


def write_summary_text(folder: RunFolder, ctx: ReportContext) -> Path:
    """The headline block alone, for a glance in a terminal."""
    lines = [f"metric      : {ctx.meta.get('metric', '')}",
             f"dataset     : {ctx.meta.get('dataset', '')}",
             f"frames      : {ctx.meta.get('n_frames', '')}",
             f"config hash : {ctx.meta.get('config_hash', '')}", ""]
    if not ctx.card.empty:
        columns = [c for c in ("field", "rho_min", "worst_axis",
                               "separability_auc_min", "gaussian_impostor_damage",
                               "flags") if c in ctx.card.columns]
        lines.append(ctx.card[columns].to_string(index=False))
    path = folder.root / "summary.txt"
    path.write_text("\n".join(lines) + "\n")
    return path


def status_line(rendered: Sequence[Rendered]) -> str:
    counts: dict[str, int] = {}
    for item in rendered:
        counts[item.status] = counts.get(item.status, 0) + 1
    return " · ".join(f"{k} {v}" for k, v in sorted(counts.items()))


# --- small helpers --------------------------------------------------------------------------


def _fmt(value: object, digits: int = 2) -> str:
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "--"
    return f"{v:.{digits}f}" if np.isfinite(v) else "--"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def _read_yaml(path: Path) -> dict[str, Any]:
    import yaml

    return yaml.safe_load(path.read_text()) if path.exists() else {}


def _dump_yaml(data: Mapping[str, Any]) -> str:
    import yaml

    return yaml.safe_dump(dict(data), sort_keys=True, default_flow_style=False)


def _read_maps(path: Path) -> dict[str, np.ndarray]:
    if not path.exists():
        return {}
    with np.load(path) as archive:
        return {k: archive[k] for k in archive.files}
