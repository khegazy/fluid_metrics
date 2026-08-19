"""One line saying what this degradation does to a field.

Replace this docstring. A degradation stands in for a way a model can be wrong, so say
which failure it imitates, not only which operation it performs.

This module must export exactly one function decorated with ``@degradation``.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from degradations.registry import degradation
from fmeval.context import FieldContext


@degradation(
    name="template_degradation",
    family="smoothing",          # one of registry.FAMILIES
    severity_name="sigma",       # what the severity number is called, e.g. "sigma"
    severity_units="cells",      # its units, shown on every axis and panel title
    severity_direction="increasing",   # does damage grow with the number, or shrink?
    calibration=None,            # None for an absolute severity; otherwise "scale",
                                 # "energy_above" or "energy_below", which resolve the
                                 # severity against each field's measured spectrum
    ordinal=True,                # False marks a canary with no ordered severity, which
                                 # is then excluded from every rank correlation
    stochastic=False,            # True redraws the random numbers on every frame
    fields=("*",),
)
def template_degradation(
    field: NDArray[np.floating],
    severity: float,
    *,
    ctx: FieldContext,
) -> NDArray[np.floating]:
    """Apply the degradation.

    Args:
        field: The field to damage, shape ``(C, *spatial)`` on the analysis grid.
        severity: The strength, already resolved against this field's calibration if the
            operator declares one. In the units named by ``severity_units``.
        ctx: Grid spacing, periodicity, the field name, the reference fluctuation RMS,
            and a random generator derived from the seed, frame and field, so results do
            not depend on iteration order.

    Returns:
        The damaged field, same shape and dtype as the input.
    """
    raise NotImplementedError("TODO(fill)")
