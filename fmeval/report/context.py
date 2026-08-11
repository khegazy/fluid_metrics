"""What a renderer receives and what it returns.

Two rules make the reporting layer maintainable.

**All non-trivial computation lives in :mod:`fmeval.analysis`.** Renderers arrange
precomputed numbers. That is what keeps a figure and its table consistent by construction,
and it means the statistics are testable without touching matplotlib.

**Renderers never write files and never mutate global state.** The driver owns paths,
formats and rcParams. So every renderer is callable from a notebook, and a run cannot
depend on the order its renderers happened to execute in.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field as dc_field
from typing import Any

import numpy as np
import pandas as pd

from .registry import RendererUnavailable
from .style import Style


@dataclass
class FigureItem:
    """One figure, plus the numbers behind it."""

    fig: Any
    keys: dict[str, str] = dc_field(default_factory=dict)
    """Slug keys, e.g. ``{"field": "vorticity"}``. Become part of the filename."""
    caption: str = ""
    data: pd.DataFrame | None = None
    """Written next to the figure as a CSV. Someone always asks for the numbers."""


@dataclass
class PlotResult:
    figures: list[FigureItem] = dc_field(default_factory=list)
    notes: list[str] = dc_field(default_factory=list)


@dataclass
class TableResult:
    """One table, rendered to both CSV and a booktabs float."""

    frame: pd.DataFrame
    keys: dict[str, str] = dc_field(default_factory=dict)
    caption: str = ""
    note: str = ""
    formats: dict[str, str] = dc_field(default_factory=dict)
    headers: dict[str, str] = dc_field(default_factory=dict)
    landscape: bool = False
    notes: list[str] = dc_field(default_factory=list)


@dataclass
class ReportContext:
    """Shared services handed to every renderer."""

    df: pd.DataFrame
    """The tidy frame, with a ``damage`` column already attached."""
    norm: pd.DataFrame
    axes: pd.DataFrame
    probes: pd.DataFrame
    card: pd.DataFrame
    spectrum: pd.DataFrame = dc_field(default_factory=pd.DataFrame)
    """Cumulative fluctuation energy against wavenumber, per field, as measured.

    Empty when the run predates the severity calibration. It is what explains the resolution a
    filter ladder has: a field holding most of its energy in one or two wavenumber shells cannot
    support a finely spaced cutoff ladder, and the curve shows that at a glance.
    """
    maps: dict[str, np.ndarray] = dc_field(default_factory=dict)
    meta: dict[str, Any] = dc_field(default_factory=dict)
    config: dict[str, Any] = dc_field(default_factory=dict)
    style: Style = dc_field(default_factory=Style)
    thresholds: Mapping[str, float] = dc_field(default_factory=dict)

    # --- graceful skip ---------------------------------------------------------------

    def require(self, condition: bool, message: str) -> None:
        """Skip this renderer, with a reason, if a data-dependent condition fails."""
        if not condition:
            raise RendererUnavailable(message)

    # --- convenience -------------------------------------------------------------------

    @property
    def ordinal_axes(self) -> list[str]:
        """Ladder axes that carry an ordering, excluding the probes."""
        from fmeval.analysis import PROBE_LABELS

        labels = self.df.loc[self.df["level"] > 0, "degradation"].unique()
        return sorted(str(a) for a in labels if a not in PROBE_LABELS)

    @property
    def metrics(self) -> list[str]:
        return sorted(str(m) for m in self.df["metric"].unique())

    @property
    def fields(self) -> list[str]:
        return sorted(str(f) for f in self.df["field"].unique())

    def axis_rows(self, **filters: str) -> pd.DataFrame:
        """Rows of the per-axis summary matching the given column values."""
        out = self.axes
        for key, value in filters.items():
            out = out[out[key] == value]
        return out

    def label(self, name: str) -> str:
        """Display form of a registry name: underscores become spaces."""
        return str(name).replace("_", " ")
