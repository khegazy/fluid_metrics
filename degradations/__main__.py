"""List the registered degradations: ``python -m degradations``.

In ``__main__.py`` rather than ``registry.py`` for the same reason as the metric
registry: ``python -m degradations.registry`` would execute the module twice and the
second copy would report an empty registry.
"""

from __future__ import annotations

from .registry import _main

if __name__ == "__main__":
    _main()
