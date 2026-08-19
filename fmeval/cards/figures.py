"""Exemplar panels: what a degradation does to a field, drawn once for the whole repo.

The layout is a grid. Columns are the original beside three severities, or the original
beside several random draws for a degradation whose severity carries no order. Rows are
the field itself followed by the diagnostics the card declares.

Four rules are enforced here rather than left to whoever generates a panel, because
breaking any of them produces a figure that is not merely ugly but misleading:

1. **Colour limits are shared across a row**, computed once and applied to every column.
   Per-panel autoscaling makes a strong degradation look identical to the original, and
   it does so silently -- the picture looks fine, and it is wrong.
2. **Difference rows take their limits from the strongest severity**, so the weak column
   is legibly faint instead of being rescaled until it looks severe.
3. **Panels are titled with the resolved severity and its units**, not with "medium".
   Several axes are calibrated per field, so the number that was configured and the number
   that was applied differ, and only the applied one describes the picture.
4. **Every figure writes the numbers behind it.** An agent reading the site cannot open a
   PNG, so each panel's summary statistics go into the fingerprint alongside it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from matplotlib import pyplot as plt
from matplotlib import rc_context

from fmeval.report import style

from .diagnostics import DIAGNOSTICS, RowContext


@dataclass(frozen=True)
class Column:
    """One column of an exemplar panel: a field and how it was produced."""

    title: str
    data: np.ndarray


@dataclass(frozen=True)
class Panel:
    """A rendered panel and the numbers behind every cell of it."""

    path: Path
    statistics: dict[str, dict[str, dict[str, float]]]
    """``{row: {column: {statistic: value}}}``, written into the fingerprint."""


def _row_limits(name: str, columns: list[Column], reference: np.ndarray) -> tuple[float, float]:
    """Colour or axis limits for one row, computed once from every column in it.

    Rules 1 and 2 live here. A field row takes its limits from the original, so the eye
    compares like with like; a signed row takes them from the largest departure anywhere
    in the row, which is the strongest severity, so weaker columns stay faint.
    """
    spec = DIAGNOSTICS[name]
    if name == "difference":
        worst = max(float(np.abs(c.data - reference).max()) for c in columns)
        return (-worst, worst) if worst > 0 else (-1.0, 1.0)
    if name == "spectral_phase":
        return (-np.pi, np.pi)
    if name == "radial_spectrum":
        from .diagnostics import _radial_spectrum

        values = [p[1:] for _, p in (_radial_spectrum(c.data) for c in columns)]
        finite = np.concatenate([v[np.isfinite(v) & (v > 0)] for v in values])
        return (float(finite.min()) * 0.5, float(finite.max()) * 2.0)
    if name == "autocorrelation":
        return (-0.5, 1.05)
    pooled = np.concatenate([np.asarray(c.data).ravel() for c in columns])
    if spec.signed:
        return style.symmetric_limits(pooled)
    return (float(np.asarray(reference).min()), float(np.asarray(reference).max()))


def exemplar_panel(
    columns: list[Column],
    rows: list[str],
    *,
    path: Path,
    title: str,
    grid: Any = None,
    dpi: int = 150,
    theme: str = "notebook",
) -> Panel:
    """Render one exemplar panel and return the numbers behind it.

    Args:
        columns: The original first, then one column per severity or draw.
        rows: Diagnostic names; ``field`` is prepended if the card did not ask for it.
        path: Where to write the PNG. Parent directories are created.
        title: Figure title, naming the degradation and the field.
        grid: Optional grid for axis extents and labels.
        dpi: Fixed so regenerating an unchanged panel produces an unchanged file.
        theme: A theme from :mod:`fmeval.report.style`, shared with the LaTeX report.

    Returns:
        The panel, with per-cell statistics keyed by row and column title.

    Raises:
        ValueError: If a row names a diagnostic that is not registered, or if fewer than
            two columns are given -- a panel with nothing to compare against is not a
            comparison.
    """
    if len(columns) < 2:
        raise ValueError(
            f"an exemplar panel needs the original and at least one degraded column, "
            f"got {len(columns)}"
        )
    unknown = [r for r in rows if r not in DIAGNOSTICS]
    if unknown:
        raise ValueError(
            f"unknown diagnostic(s) {unknown}; registered: {sorted(DIAGNOSTICS)}"
        )
    if rows and rows[0] != "field":
        rows = ["field", *[r for r in rows if r != "field"]]

    reference = np.asarray(columns[0].data)
    styling = style.Style.build(theme)
    statistics: dict[str, dict[str, dict[str, float]]] = {}

    with rc_context(styling.rc):
        fig, axes = plt.subplots(
            len(rows), len(columns), squeeze=False,
            figsize=(styling.panel_w * len(columns), styling.panel_h * len(rows)),
        )
        for r, row_name in enumerate(rows):
            spec = DIAGNOSTICS[row_name]
            limits = _row_limits(row_name, columns, reference)
            ctx = RowContext(reference=reference, grid=grid, limits=limits,
                             extra={"nyquist": reference.shape[-1] // 2})
            statistics[row_name] = {}
            for c, column in enumerate(columns):
                ax = axes[r][c]
                statistics[row_name][column.title] = spec.fn(ax, column.data, ctx)
                if r == 0:
                    ax.set_title(column.title, fontsize="small")
                if c == 0:
                    ax.set_ylabel(spec.label, fontsize="small")
                if row_name in ("field", "difference", "spectral_phase"):
                    ax.set_xticks([])
                    ax.set_yticks([])
            # Rule 1, made visible: say what the shared limits were.
            axes[r][-1].text(
                1.02, 0.5, f"[{limits[0]:.3g}, {limits[1]:.3g}]",
                transform=axes[r][-1].transAxes, rotation=90,
                va="center", ha="left", fontsize="xx-small", color="0.4",
            )
        fig.suptitle(title, fontsize="medium")
        fig.set_layout_engine("tight")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Strip the creation-date metadata matplotlib writes by default: without this,
        # every regeneration is a byte diff on an unchanged figure and the review signal
        # drowns in noise.
        fig.savefig(path, dpi=dpi, metadata={"Software": None})
        plt.close(fig)

    return Panel(path=path, statistics=statistics)
