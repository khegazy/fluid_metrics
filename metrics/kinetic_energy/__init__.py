"""Kinetic energy: a reference-free diagnostic of the flow's energy content.

Importing this package registers the metric. See ``card.md`` for what it measures, how to
read it, and where it misleads.
"""

from __future__ import annotations

from .metric import kinetic_energy

__all__ = ["kinetic_energy"]
