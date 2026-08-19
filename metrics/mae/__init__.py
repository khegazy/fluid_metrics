"""Mean absolute error: the pointwise L1 control.

Importing this package registers the metric and its pointwise map. See ``card.md`` for
what it measures, how to read it, and where it misleads.
"""

from __future__ import annotations

from .metric import mae, mae_map

__all__ = ["mae", "mae_map"]
