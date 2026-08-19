"""Enstrophy: a reference-free diagnostic of small-scale rotational activity.

Importing this package registers the metric. See ``card.md`` for what it measures, how to
read it, and where it misleads.
"""

from __future__ import annotations

from .metric import enstrophy

__all__ = ["enstrophy"]
