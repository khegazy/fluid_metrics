"""One line saying what this metric measures.

Replace this docstring. It is quoted directly into the generated report, so write it for
someone who has not read the card: what the number is, not how the code works.

This module must export exactly one function decorated with ``@metric``. The registry
finds it by walking the package, so there is nothing to register anywhere else.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from metrics.registry import metric


@metric(
    name="template_metric",
    arity="pairwise",        # "pairwise" -> fn(reference, candidate); "single" -> fn(x)
    fields=("*",),           # canonical fields this accepts; ("*",) for any
    returns="scalar",
    differentiable=True,     # declared, never inferred: could this be a training loss?
    cost="cheap",            # cheap | moderate | expensive (advisory)
    higher_is_better=False,
    symmetric=True,          # enables an automatic symmetry check
    units="field",           # e.g. "field", "field^2", "dimensionless"
)
def template_metric(
    reference: NDArray[np.floating],
    candidate: NDArray[np.floating],
) -> float:
    """Compute the metric.

    Cite any equation taken from a paper in a comment here, with the equation number,
    and put the entry in this bundle's ``refs.bib``.

    Args:
        reference: The trusted field, shape ``(C, *spatial)`` on the analysis grid.
        candidate: The field being scored, same shape and grid.

    Returns:
        One float. The evaluation loop handles fields, frames and severity levels, so
        this function sees one pair at a time and returns one number.
    """
    raise NotImplementedError("TODO(fill)")
