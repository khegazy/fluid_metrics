"""Specific kinetic energy: a reference-free physics diagnostic.

A single-field metric, evaluated on the reference and on every degraded variant so that
``fmeval.analysis`` can derive the drift.
"""

from __future__ import annotations

import numpy as np

from ..registry import metric


@metric(
    name="kinetic_energy",
    arity="single",
    fields=("velocity",),
    returns="scalar",
    differentiable=True,
    cost="cheap",
    higher_is_better=False,   # no direction of its own: the drift from the reference is what is read
    symmetric=False,
    units="field^2",
)
def kinetic_energy(x: np.ndarray) -> float:
    """Mean specific kinetic energy, one half the mean squared velocity magnitude.

    Density-weighted energy is the conserved quantity, but at Mach 0.1 with density
    varying under 4% the two differ negligibly, and this form needs only one field.

    Parameters
    ----------
    x
        Velocity on the analysis grid, shape ``(C, *spatial)``. Components are summed
        before averaging over cells.

    Returns
    -------
    float
        ``0.5 * <|u|^2>``, in the square of the velocity units.
    """
    return float(0.5 * (x**2).sum(axis=0).mean())
