"""The evaluation harness: data readers, the degradation ladder, analysis and reporting.

Importing this package installs one thing: the card validator, which makes the metric and
degradation registries refuse to hand back something whose documentation is missing or
disagrees with the code. It is installed here, rather than inside the registries, so that
``import metrics`` on its own stays free of this package's dependencies, and so that a
half-written card in one bundle cannot break a run of an unrelated metric. See
``fmeval/cards/loader.py`` for the reasoning in full.

Nothing else is re-exported. Modules are imported by their full path, so that a reader
following an import knows exactly which file to open.
"""

from __future__ import annotations


def _install_card_validator() -> None:
    """Wire up card enforcement, tolerating an incomplete checkout.

    A failure here must not stop the harness importing: the validator is a guard rail, and
    a broken guard rail should be visible without also making the tool unusable.
    """
    try:
        from .cards.loader import install

        install()
    except Exception:  # deliberately broad - see docstring
        import logging

        logging.getLogger(__name__).debug("card validation unavailable", exc_info=True)


_install_card_validator()
