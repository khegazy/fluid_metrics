"""Mean squared error: the pointwise L2 control.

Importing this package registers the metric and its pointwise map. See ``card.md`` for
what it measures, how to read it, and where it misleads.
"""

from __future__ import annotations

from .metric import mse, mse_map

__all__ = ["mse", "mse_map"]
