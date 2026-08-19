"""Metric functions for evaluating fluid-simulation quality.

Add a metric by writing one decorated function in any module or subpackage under
``metrics/``; discovery walks the package, so there is no import list to update::

    from metrics.registry import metric

    @metric(arity="pairwise", fields=("vorticity",), units="field")
    def h_minus_one(reference, candidate, *, ctx):
        '''Homogeneous negative Sobolev norm of the difference.'''
        ...

Keep heavy imports (torch, gudhi, ...) inside the function body rather than at module
level: every metric module is imported on every run, so a module-level heavy import is a
startup cost paid by everyone, including runs that do not use that metric.

This module deliberately does *not* call ``discover()`` at import time -- that would create
an import cycle and make ``import metrics.registry`` drag in every metric. ``get()`` and
``available()`` trigger discovery lazily.
"""

from __future__ import annotations

from .registry import (
    REGISTRY,
    MetricSpec,
    available,
    discover,
    get,
    metric,
    pointwise_map,
)

__all__ = [
    "REGISTRY",
    "MetricSpec",
    "available",
    "discover",
    "get",
    "metric",
    "pointwise_map",
]
