"""Reference-free physics diagnostics.

These are single-field (``arity="single"``) metrics: they characterise one field rather
than comparing two. The pipeline evaluates them on the reference and on every degraded
variant, and `analysis.py` derives the drift from that.

Enstrophy ships on day one mainly so the single-field code path is exercised end to end
from the first run, rather than being discovered broken three weeks later. Both quantities
here are single scalars and individually degenerate -- many wrong fields share a given
enstrophy -- so they are tripwires rather than verdicts.
"""

from __future__ import annotations

import numpy as np

from ..registry import metric


@metric(
    name="enstrophy",
    arity="single",
    fields=("vorticity",),
    returns="scalar",
    differentiable=True,
    cost="cheap",
    higher_is_better=False,
    symmetric=False,
    units="field^2",
)
def enstrophy(x: np.ndarray) -> float:
    """Mean enstrophy, 0.5 * <|omega|^2>, summed over vorticity components.

    In 2D vorticity has one component; in 3D it has three and they are summed before
    averaging over cells.
    """
    return float(0.5 * (x**2).sum(axis=0).mean())


@metric(
    name="kinetic_energy",
    arity="single",
    fields=("velocity",),
    returns="scalar",
    differentiable=True,
    cost="cheap",
    higher_is_better=False,
    symmetric=False,
    units="field^2",
)
def kinetic_energy(x: np.ndarray) -> float:
    """Mean specific kinetic energy, 0.5 * <|u|^2>, summed over velocity components.

    Density-weighted energy would be the conserved quantity; at Ma = 0.1 with density
    varying under 4% the two differ negligibly, and this form needs only one field.
    """
    return float(0.5 * (x**2).sum(axis=0).mean())
