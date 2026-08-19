"""Axis selection for the geometric operators."""

from __future__ import annotations


def _axes_for(direction: str, ctx) -> tuple[int, ...]:
    """Resolve a direction name to negative array axes via the grid's dims.

    Never hardcode -1 or -2: which axis is "x" depends on how many spatial dimensions
    there are.
    """
    if direction == "diag":
        return ctx.spatial_axes
    return (ctx.axis(direction),)
