"""Registries for plots and tables, and the section sequence they slot into.

Adding a figure is one decorated function plus a section number. ``section`` and ``order``
place it in the narrative; the writer groups by section and emits them in order, so no
dispatch list needs editing.

Unavailability is declarative first. ``requires_columns``, ``requires_degradations``,
``min_metrics`` and so on are checked *before* the function is entered, which covers most
cases at no cost inside the renderer -- a cross-metric figure on a single-metric run, or
the IN-4 panel when that field was not evaluated. Data-dependent cases raise
:class:`RendererUnavailable` from inside.

Unlike metrics and degradations, renderers are found by explicit import rather than a
package walk: they are a small closed set maintained with the harness, so the discovery
mechanism that suits an open contributor set would only add indirection here.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field as dc_field
from typing import Any, Literal

import pandas as pd

Scope = Literal["global", "per_field", "per_metric", "per_metric_field"]


class RendererUnavailable(Exception):
    """Raised by a renderer that cannot run on the data it was given.

    Not an error: the driver logs it, records the reason in the manifest, and moves on.
    """


@dataclass
class Section:
    """One chapter of the report."""

    number: int
    key: str
    title: str
    intro: str = ""


#: The narrative. State what the thing is, then whether it works at all, then whether it
#: works reliably, then what it detects, then try to break it, and only then cost and
#: caveats. Adversarial checks come late because they mean nothing if the basic response
#: already failed, and the eye-calibration figures sit next to the numbers that claim
#: where the metric fires.
SECTIONS: tuple[Section, ...] = (
    Section(1, "overview", "What this is",
            "Identity of the metric under test and of the run that produced these "
            "numbers."),
    Section(2, "headline", "Headline",
            "The few numbers worth reading before any detail."),
    Section(3, "response", "Does it see damage?",
            "Whether the metric responds at all as each degradation is made worse. If "
            "these curves are flat, nothing below matters."),
    Section(4, "reliability", "Is the response reliable?",
            "Rank correlation with degradation severity, computed within each ladder "
            "axis and never across, with an interval that accounts for the "
            "autocorrelation of the trace in time."),
    Section(5, "separability", "Can it separate adjacent severity levels?",
            "Monotone medians are not sufficient. If the distributions of adjacent severity levels "
            "overlap, the metric cannot rank two models that differ by one step."),
    Section(6, "sensitivity", "When and where does it fire?",
            "The severity level at which the metric first departs from its clean value, the severity level at "
            "which it saturates, and what the field actually looks like at each -- so the "
            "numbers can be checked against the eye."),
    Section(7, "selectivity", "What does it detect?",
            "Response across every ladder axis. A metric whose profile is uniform is "
            "responding to damage in general rather than to a specific failure mode."),
    Section(8, "robustness", "Can it be fooled?",
            "Fields constructed to be misleading: the spectrum-matched Gaussian field, "
            "which preserves the energy spectrum exactly while destroying all phase "
            "information, and the positionally unrelated field, which preserves every "
            "statistic while destroying alignment."),
    Section(9, "displacement", "Displacement",
            "The central pathology this project exists to address: a feature that is "
            "correct in shape and amplitude but slightly displaced."),
    Section(10, "cost", "Cost",
            "Wall-clock per evaluation and its projection to a full trajectory."),
    Section(11, "reproducibility", "Caveats and reproducibility",
            "What was skipped and why, the provenance of the run, and the exact "
            "configuration that produced these numbers."),
    Section(12, "complexity", "Does it hold as complexity rises?",
            "Behaviour across datasets of increasing physical complexity. Omitted unless "
            "several datasets of one family are present."),
)
SECTIONS_BY_NUMBER: dict[int, Section] = {s.number: s for s in SECTIONS}


@dataclass(frozen=True)
class RendererSpec:
    """Everything the driver knows about one plot or table."""

    name: str
    fn: Callable
    kind: Literal["plot", "table"]
    section: int
    order: int
    title: str
    doc: str
    scope: Scope
    requires_columns: tuple[str, ...]
    requires_degradations: tuple[str, ...]
    min_metrics: int
    min_axes: int
    min_frames: int
    min_datasets: int
    requires_maps: bool
    defaults: dict[str, Any] = dc_field(default_factory=dict)


PLOTS: dict[str, RendererSpec] = {}
TABLES: dict[str, RendererSpec] = {}


def _register(bucket: dict[str, RendererSpec], kind: str, **kw):
    def _decorate(fn: Callable) -> Callable:
        name = kw.pop("name", None) or fn.__name__
        if name in bucket:
            raise ValueError(
                f"duplicate {kind} {name!r}: {bucket[name].fn.__module__} vs {fn.__module__}"
            )
        section = kw.pop("section")
        if section not in SECTIONS_BY_NUMBER:
            raise ValueError(
                f"{name}: section {section} is not one of {sorted(SECTIONS_BY_NUMBER)}"
            )
        bucket[name] = RendererSpec(
            name=name,
            fn=fn,
            kind=kind,
            section=section,
            order=kw.pop("order", 100),
            title=kw.pop("title", name.replace("_", " ")),
            doc=(fn.__doc__ or "").strip(),
            scope=kw.pop("scope", "global"),
            requires_columns=tuple(kw.pop("requires_columns", ())),
            requires_degradations=tuple(kw.pop("requires_degradations", ())),
            min_metrics=kw.pop("min_metrics", 1),
            min_axes=kw.pop("min_axes", 0),
            min_frames=kw.pop("min_frames", 1),
            min_datasets=kw.pop("min_datasets", 1),
            requires_maps=kw.pop("requires_maps", False),
            defaults=dict(kw.pop("defaults", {}) or {}),
        )
        if kw:
            raise TypeError(f"{name}: unexpected registration keys {sorted(kw)}")
        return fn

    return _decorate


def plot(**kw):
    """Register a figure renderer. Signature: ``fn(ctx, df, opts) -> PlotResult``."""
    return _register(PLOTS, "plot", **kw)


def table(**kw):
    """Register a table renderer. Signature: ``fn(ctx, df, opts) -> TableResult``."""
    return _register(TABLES, "table", **kw)


def iter_renderers() -> list[RendererSpec]:
    """Every registered renderer, in narrative order."""
    return sorted([*PLOTS.values(), *TABLES.values()],
                  key=lambda s: (s.section, s.order, s.name))


def check_preconditions(spec: RendererSpec, ctx) -> tuple[bool, str]:
    """Whether ``spec`` can run, and why not if it cannot.

    Checked before the renderer is entered, so most unavailability costs nothing inside
    the function and produces a clear reason rather than an exception.
    """
    df = ctx.df
    missing = [c for c in spec.requires_columns if c not in df.columns]
    if missing:
        return False, f"missing column(s) {missing}"
    present = set(df["degradation"].unique()) if "degradation" in df.columns else set()
    absent = [d for d in spec.requires_degradations if d not in present]
    if absent:
        return False, f"ladder has no {absent}"
    if df.empty:
        return False, "no rows"
    if df["metric"].nunique() < spec.min_metrics:
        return False, f"needs {spec.min_metrics} metrics, has {df['metric'].nunique()}"
    n_axes = df.loc[df["level"] > 0, "degradation"].nunique()
    if n_axes < spec.min_axes:
        return False, f"needs {spec.min_axes} ladder axes, has {n_axes}"
    if df["frame_index"].nunique() < spec.min_frames:
        return False, f"needs {spec.min_frames} frames, has {df['frame_index'].nunique()}"
    if df["dataset"].nunique() < spec.min_datasets:
        return False, f"needs {spec.min_datasets} datasets, has {df['dataset'].nunique()}"
    if spec.requires_maps and not ctx.maps:
        return False, "no pointwise metric maps were stored"
    return True, ""


def iter_scope(scope: Scope, df: pd.DataFrame):
    """Split a frame according to a renderer's scope, yielding ``(keys, subset)``."""
    if scope == "global":
        yield {}, df
        return
    columns = {
        "per_field": ["field"],
        "per_metric": ["metric"],
        "per_metric_field": ["metric", "field"],
    }[scope]
    for values, sub in df.groupby(columns, observed=True):
        values = values if isinstance(values, tuple) else (values,)
        yield dict(zip(columns, (str(v) for v in values))), sub
