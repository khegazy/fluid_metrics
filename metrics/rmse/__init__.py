"""Root mean squared error: the pointwise L2 control in the field's own units.

Importing this package registers the metric and its pointwise map. See ``card.md`` for
what it measures, how to read it, and where it misleads.
"""

from __future__ import annotations

from .metric import rmse, rmse_map

__all__ = ["rmse", "rmse_map"]
