"""Figure style: palette, themes, and the one place ``imshow`` is allowed.

Two rules here prevent whole classes of misleading figure.

**Field images go through :func:`show_field`.** Data is stored ``(X, Y)``, so a naive
``imshow`` puts x on the vertical axis and silently transposes every picture in the
report. Every real grid is square, so a transposed figure looks entirely plausible and
nothing catches it. Centralising the call means the transpose is applied once and a lint
test can assert ``imshow`` appears nowhere else.

**Colour assignment is deterministic.** Metric and axis colours are built once from the
sorted unique values, so a metric is the same colour in every figure and in every rerun.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any, Literal

import matplotlib

matplotlib.use("Agg")  # compute nodes have no display; must precede the pyplot import

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, to_rgb  # noqa: E402

Theme = Literal["notebook", "paper"]

#: Okabe-Ito: colourblind-safe, and legible in greyscale when paired with line styles.
OKABE_ITO: dict[str, str] = {
    "black": "#000000",
    "orange": "#E69F00",
    "sky": "#56B4E9",
    "green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "purple": "#CC79A7",
}
_CYCLE = ["blue", "vermillion", "green", "orange", "purple", "sky", "black", "yellow"]

#: Line styles carry the same information as hue, so a greyscale print stays readable.
LINE_STYLES = ("-", "--", ":", "-.", (0, (3, 1, 1, 1)), (0, (5, 2)))

_THEMES: dict[str, dict[str, Any]] = {
    "notebook": {
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "font.size": 10,
        "axes.labelsize": 10,
        "axes.titlesize": 11,
        "legend.fontsize": 9,
    },
    "paper": {
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "font.size": 8.5,
        "axes.labelsize": 9,
        "axes.titlesize": 9.5,
        "legend.fontsize": 8,
        # Type 42 keeps text editable and embeddable, which most publishers require.
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "mathtext.fontset": "cm",
    },
}
_COMMON: dict[str, Any] = {
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.constrained_layout.use": True,
}


def okabe(name: str) -> str:
    """A palette colour by name, so no renderer hardcodes a hex value."""
    return OKABE_ITO[name]


@dataclass
class Style:
    """Palette, rcParams and figure sizing for one report."""

    theme: Theme = "notebook"
    panel_w: float = 3.3
    panel_h: float = 2.5
    max_size: float = 20.0
    metric_colours: dict[str, str] = dc_field(default_factory=dict)
    axis_colours: dict[str, str] = dc_field(default_factory=dict)
    axis_styles: dict[str, Any] = dc_field(default_factory=dict)

    @classmethod
    def build(cls, theme: Theme = "notebook", *, metrics=(), axes=()) -> Style:
        """Assign colours once, from the sorted unique values, so reruns agree."""
        style = cls(theme=theme)
        if theme == "paper":
            style.panel_w, style.panel_h = 2.3, 1.9
        for i, name in enumerate(sorted(set(metrics))):
            style.metric_colours[name] = okabe(_CYCLE[i % len(_CYCLE)])
        for i, name in enumerate(sorted(set(axes))):
            style.axis_colours[name] = okabe(_CYCLE[i % len(_CYCLE)])
            style.axis_styles[name] = LINE_STYLES[i % len(LINE_STYLES)]
        return style

    @property
    def rc(self) -> dict[str, Any]:
        return {**_COMMON, **_THEMES[self.theme]}

    def metric_colour(self, name: str) -> str:
        return self.metric_colours.get(name, okabe("blue"))

    def axis_colour(self, name: str) -> str:
        return self.axis_colours.get(name, okabe("blue"))

    def axis_style(self, name: str) -> Any:
        return self.axis_styles.get(name, "-")

    def level_colours(self, base: str, n: int) -> list[str]:
        """A lightness ramp within one hue: family by colour, rung by lightness.

        Keeps twenty series readable when they are faceted a handful at a time.
        """
        if n <= 1:
            return [base]
        rgb = np.array(to_rgb(base))
        light = 1 - 0.75 * (1 - rgb)
        dark = 0.55 * rgb
        cmap = LinearSegmentedColormap.from_list("ramp", [light, rgb, dark])
        return [cmap(v) for v in np.linspace(0.15, 1.0, n)]

    def figure(self, nrows: int = 1, ncols: int = 1, *,
               w: float | None = None, h: float | None = None, **kwargs):
        """A figure sized from the panel grid, capped so nothing becomes unplottable.

        Args:
            nrows, ncols: Grid dimensions. Integers -- these are subplot counts, not sizes.
            w, h: Explicit figure size in inches, overriding the panel arithmetic. For
                figures whose natural size follows the data (a heatmap of N metrics by M
                axes) rather than a panel count.
        """
        width = min(w if w is not None else self.panel_w * ncols, self.max_size)
        height = min(h if h is not None else self.panel_h * nrows, self.max_size)
        return plt.subplots(int(nrows), int(ncols), figsize=(width, height),
                            squeeze=False, **kwargs)


def show_field(ax, data: np.ndarray, grid=None, **kwargs):
    """Draw a 2-D field. **The only place any renderer may call ``imshow``.**

    Data is ``(X, Y)``: x varies along axis 0. Matplotlib's ``imshow`` puts axis 0 on the
    vertical, so the array is transposed here and ``origin="lower"`` is set, giving x
    horizontal and y vertical as a reader expects. Doing this per renderer would guarantee
    that one of them eventually forgets, and on square data the result looks fine.

    Args:
        ax: Target axes.
        data: ``(X, Y)`` array. A leading channel axis of length 1 is squeezed.
        grid: Optional :class:`~fmeval.data.base.GridSpec` for axis labels and extent.
        **kwargs: Passed to ``imshow``; ``cmap`` and ``vmin``/``vmax`` are the usual ones.
    """
    array = np.asarray(data)
    if array.ndim == 3 and array.shape[0] == 1:
        array = array[0]
    if array.ndim != 2:
        raise ValueError(f"show_field needs a 2-D field, got shape {array.shape}")

    extent = None
    if grid is not None:
        lx, ly = grid.length[0], grid.length[1]
        extent = (0.0, lx, 0.0, ly)
    kwargs.setdefault("interpolation", "nearest")
    image = ax.imshow(array.T, origin="lower", extent=extent, aspect="equal", **kwargs)
    if grid is not None:
        ax.set_xlabel(grid.dims[0])
        ax.set_ylabel(grid.dims[1])
    ax.grid(False)
    return image


def symmetric_limits(data: np.ndarray, quantile: float = 1.0) -> tuple[float, float]:
    """Limits centred on zero, for a signed field on a diverging colour map."""
    finite = np.asarray(data)[np.isfinite(data)]
    if finite.size == 0:
        return (-1.0, 1.0)
    v = float(np.quantile(np.abs(finite), quantile))
    return (-v, v) if v > 0 else (-1.0, 1.0)


def finish(fig, legend_handles=None, legend_labels=None, ncol: int = 4) -> None:
    """Deduplicated figure-level legend, placed outside the axes."""
    if legend_handles:
        fig.legend(legend_handles, legend_labels, loc="lower center",
                   ncol=ncol, frameon=False, bbox_to_anchor=(0.5, -0.02))
