"""Normalised root mean squared error: RMSE divided by the reference fluctuation.

Importing this package registers the metric. See ``card.md`` for what it measures, how to
read it, and where it misleads.
"""

from __future__ import annotations

from .metric import nrmse

__all__ = ["nrmse"]
