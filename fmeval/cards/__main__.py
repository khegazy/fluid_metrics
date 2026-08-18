"""Entry point for ``python -m fmeval.cards``.

The implementation lives in :mod:`fmeval.cards.cli` rather than here, for the same reason
``metrics/__main__.py`` defers to its registry: running ``python -m fmeval.cards.cli``
would execute that module a second time under the name ``__main__``, giving it its own
copy of any module-level state and a confusing result.
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
