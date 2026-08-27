"""A card's links must resolve both in the repository and on the documentation site.

A card is read in two places and is the same bytes in both: a colleague browsing the
repository on GitHub, and a reader on the generated site. Only some paths work in both.
`docs/gen_pages.py` rewrites card-to-card links, and `_generated/` assets are copied
alongside the page -- but a relative link to anything the site does not publish resolves
on GitHub and 404s on the site, which `mkdocs --strict` treats as a build failure.

`issues/` is the case that bites: it is deliberately not part of the site, so a card that
links to an issue by relative path breaks the build. Such a link has to be absolute.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

#: Every markdown link target in a card, excluding images.
_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")

#: Repository directories the documentation site does not publish. A relative link into
#: one of these resolves on GitHub and 404s on the site.
UNPUBLISHED = ("issues/",)

CARDS = sorted(REPO.glob("metrics/*/card.md")) + sorted(REPO.glob("degradations/*/card.md"))


@pytest.mark.parametrize("card", CARDS, ids=[c.parent.name for c in CARDS])
def test_no_relative_link_into_an_unpublished_directory(card):
    """Link to an issue absolutely, so the same text works in both places."""
    offenders = []
    for target in _LINK.findall(card.read_text()):
        if target.startswith(("http://", "https://", "#")):
            continue
        if any(part in target for part in UNPUBLISHED):
            offenders.append(target)
    assert not offenders, (
        f"{card.parent.name}/card.md links to {offenders} by relative path. That "
        "resolves on GitHub and 404s on the site, which fails `mkdocs --strict`. Use the "
        "full https://github.com/... URL instead."
    )


@pytest.mark.parametrize("card", CARDS, ids=[c.parent.name for c in CARDS])
def test_relative_links_point_at_something_that_exists(card):
    """A relative link that resolves nowhere in the repository is simply broken."""
    missing = []
    for target in _LINK.findall(card.read_text()):
        if target.startswith(("http://", "https://", "#")):
            continue
        path = (card.parent / target.split("#", 1)[0]).resolve()
        if not path.exists():
            missing.append(target)
    assert not missing, f"{card.parent.name}/card.md links to missing files: {missing}"
