"""List the registered metrics: ``python -m metrics``.

This lives in ``__main__.py`` rather than behind ``if __name__ == "__main__"`` in
``registry.py`` on purpose. ``python -m metrics.registry`` would execute ``registry`` a
second time under the name ``__main__``, giving that copy its own empty ``REGISTRY`` while
the decorators populate the original -- so it would always report zero metrics.
"""

from __future__ import annotations

from .registry import _main

if __name__ == "__main__":
    _main()
