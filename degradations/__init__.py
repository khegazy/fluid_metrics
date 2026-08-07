"""Degradation operators: controlled ways of damaging a reference field.

Which failure modes you probe determines what the acceptance measurements actually mean,
so "how the data is broken" is as extensible as "what is measured". Add one by writing a
decorated function in any module under ``degradations/``::

    from degradations.registry import degradation

    @degradation(family="smoothing", severity_name="sigma", severity_units="cells")
    def my_blur(x, severity, *, ctx):
        '''One-line description; shown by `python -m degradations`.'''
        ...

Operators take one field, ``(C, *spatial)``, and return the same shape. Discovery is
lazy -- see the note in ``metrics/__init__.py`` for why this module does not call it.
"""

from __future__ import annotations

from .registry import (
    FAMILIES,
    REGISTRY,
    DegradationSpec,
    available,
    degradation,
    discover,
    get,
)

__all__ = [
    "FAMILIES",
    "REGISTRY",
    "DegradationSpec",
    "available",
    "degradation",
    "discover",
    "get",
]
